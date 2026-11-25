# [负责人：邓春鹏 | 核心交付 | 对接：周世航(models 字段核对)、方成朋(检索测试用例 TC-08/TE-02)]
"""M3 分类检索查询构建器（app/services/query_builder.py）

对应《非遗数字化管理平台系统分析与设计报告》：
- 业务规则：BR-02（管理者范围）、BR-07（公开条件）、BR-10（软删除）
- 接口与用例：API-10（GET /projects）、UC-03、TC-08、TE-02
- 核心能力：公开/范围过滤、省市县三级地区级联、M:N 标签防重、排序白名单、二级稳定分页
"""

from __future__ import annotations

from collections import deque
from typing import Iterable, Optional, Sequence

from sqlalchemy import func, or_

# 按报告目录结构（代码 6-1），模型定义在 app/models.py 中；
# 实际集成时请与组长（周世航）核对字段名是否一致（特别是 summary 与软删除字段）。
from app.models import Certification, Project, ProjectDetail, Region, Tag


class QueryValidationError(ValueError):
    """查询参数非法（路由层统一映射为 HTTP 400，覆盖 TE-02）。"""


class QueryPermissionError(PermissionError):
    """无权使用请求的查询范围（路由层统一映射为 HTTP 403）。"""


class ProjectQueryBuilder:
    """非遗项目链式查询构建器（基于 Flask-SQLAlchemy）。"""

    # 排序字段严格白名单（对应 1.1 节四种排序 + TE-02 注入拦截）
    # 所有排序末尾都会统一追加 Project.id.desc() 保证翻页稳定（对应 TC-08）
    SORT_WHITELIST = {
        "views": Project.views.desc(),
        "updated_at": Project.updated_at.desc(),
        "created_at": Project.created_at.desc(),
        "archived_at": Project.archived_at.desc().nullslast(),
    }

    DEFAULT_SORT = "updated_at"
    DEFAULT_PER_PAGE = 12  # 对应 UC-03 / TC-08：分页返回 12 条

    def __init__(self, base_query=None) -> None:
        self._query = base_query if base_query is not None else Project.query
        # 统一排除软删除记录（BR-10）
        # 注：若 models.py 采用 deleted_at 字段，请改为 Project.deleted_at.is_(None)
        self._query = self._query.filter(Project.status != "deleted")
        self._sorted = False

    # ------------------------------------------------------------------
    # 1. 可见性与角色范围过滤（BR-02 / BR-07）
    # ------------------------------------------------------------------
    def apply_scope(self, user=None, scope: str = "public") -> "ProjectQueryBuilder":
        """根据当前用户与 scope 参数收口数据范围。

        scope 取值：
        - "public"：默认公众视图，仅返回 status='published' 且 visibility='public'
        - "mine"：项目管理者查看自己创建或已通过认证（approved）的项目
        - "all"：管理员/系统管理员查看全部未软删除项目
        """
        scope = (scope or "public").strip().lower()
        if scope not in {"public", "mine", "all"}:
            raise QueryValidationError(f"非法的 scope 参数: {scope}")

        if scope == "public":
            self._query = self._query.filter(
                Project.status == "published",
                Project.visibility == "public",
            )
            return self

        # scope 为 mine 或 all 时必须已登录
        is_authenticated = bool(user and getattr(user, "is_authenticated", False))
        if not is_authenticated:
            raise QueryPermissionError("未登录用户仅可浏览公开项目")

        role = getattr(user, "role", "")

        if scope == "all":
            if role not in {"admin", "sysadmin"}:
                raise QueryPermissionError("仅管理员可查看全部项目")
            return self

        # scope == "mine"
        if role in {"admin", "sysadmin"}:
            self._query = self._query.filter(Project.owner_id == user.id)
        elif role == "manager":
            approved_project_ids = (
                Certification.query.with_entities(Certification.project_id)
                .filter(
                    Certification.user_id == user.id,
                    Certification.status == "approved",
                )
                .subquery()
            )
            self._query = self._query.filter(
                or_(
                    Project.owner_id == user.id,
                    Project.id.in_(approved_project_ids),
                )
            )
        else:
            raise QueryPermissionError("普通用户无个人项目管理视图")

        return self

    def filter_status(self, status: Optional[str]) -> "ProjectQueryBuilder":
        """后台或个人视图按状态筛选（不可查 deleted）。"""
        if not status:
            return self
        allowed_statuses = {"draft", "pending", "published", "rejected", "archived"}
        if status not in allowed_statuses:
            raise QueryValidationError(f"非法的项目状态: {status}")
        self._query = self._query.filter(Project.status == status)
        return self

    # ------------------------------------------------------------------
    # 2. 分类体系筛选：三级地区树级联、十大门类、M:N 标签防重
    # ------------------------------------------------------------------
    @staticmethod
    def get_descendant_region_ids(region_id: int) -> list[int]:
        """获取指定地区节点及其所有下级（市/县）ID 列表。

        采用一次查表 + 内存 BFS（地区表记录数小，避免 SQLite 递归 CTE 兼容问题）。
        """
        rows = Region.query.with_entities(Region.id, Region.parent_id).all()
        children_map: dict[Optional[int], list[int]] = {}
        existing_ids: set[int] = set()

        for rid, pid in rows:
            existing_ids.add(rid)
            children_map.setdefault(pid, []).append(rid)

        if region_id not in existing_ids:
            return []

        result: list[int] = []
        queue = deque([region_id])
        visited: set[int] = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            for child_id in children_map.get(current, []):
                if child_id not in visited:
                    queue.append(child_id)

        return result

    def filter_region(self, region_id: Optional[int]) -> "ProjectQueryBuilder":
        """按地区筛选（选中省或市时自动级联包含其下属市/县项目）。"""
        if region_id is None:
            return self
        region_ids = self.get_descendant_region_ids(int(region_id))
        if not region_ids:
            # 地区不存在时返回空集而非报错，与前端空状态兼容
            self._query = self._query.filter(Project.id == -1)
            return self
        self._query = self._query.filter(Project.region_id.in_(region_ids))
        return self

    def filter_category(self, category_id: Optional[int]) -> "ProjectQueryBuilder":
        """按国家级非遗十大门类筛选。"""
        if category_id is None:
            return self
        self._query = self._query.filter(Project.category_id == int(category_id))
        return self

    def filter_tags(
        self,
        tag_ids: Optional[Sequence[int] | Iterable[int]],
        match_mode: str = "all",
    ) -> "ProjectQueryBuilder":
        """按 M:N 标签筛选，使用 EXISTS（.any()）彻底避免 JOIN 导致的分页重复行。

        match_mode:
        - "all"（默认）：交集（AND），项目需同时包含所有所选标签
        - "any"：并集（OR），项目包含任一所选标签即可
        """
        if not tag_ids:
            return self

        normalized_ids = sorted({int(tid) for tid in tag_ids})
        if not normalized_ids:
            return self

        if match_mode == "all":
            for tid in normalized_ids:
                self._query = self._query.filter(Project.tags.any(Tag.id == tid))
        elif match_mode == "any":
            self._query = self._query.filter(Project.tags.any(Tag.id.in_(normalized_ids)))
        else:
            raise QueryValidationError(f"非法的标签匹配模式: {match_mode}")

        return self

    # ------------------------------------------------------------------
    # 3. 关键词检索（标题 + 详情正文，全参数化防 SQL 注入）
    # ------------------------------------------------------------------
    def filter_keyword(self, keyword: Optional[str]) -> "ProjectQueryBuilder":
        """按关键词模糊搜索标题、摘要与详情内容。"""
        if not keyword or not keyword.strip():
            return self

        kw = f"%{keyword.strip()}%"
        conditions = [Project.title.ilike(kw)]

        # 兼容 models.py 中是否单独定义了 Project.summary 列（BR-01 必填摘要）
        if hasattr(Project, "summary"):
            conditions.append(Project.summary.ilike(kw))

        # 通过 1:1 关联检查 ProjectDetail.content，使用 has() 避免 JOIN 重复行
        if hasattr(Project, "detail"):
            conditions.append(
                Project.detail.has(
                    or_(
                        ProjectDetail.content.ilike(kw),
                        ProjectDetail.history.ilike(kw),
                        ProjectDetail.protection.ilike(kw),
                    )
                )
            )

        self._query = self._query.filter(or_(*conditions))
        return self

    # ------------------------------------------------------------------
    # 4. 排序白名单 + 二级稳定排序 + 分页（TC-08 / TE-02）
    # ------------------------------------------------------------------
    def apply_sort(self, sort_key: Optional[str] = None) -> "ProjectQueryBuilder":
        """按严格白名单排序，并固定追加 Project.id DESC 作为二级排序保证翻页稳定。"""
        key = (sort_key or self.DEFAULT_SORT).strip()
        if key not in self.SORT_WHITELIST:
            raise QueryValidationError(
                f"非法的排序字段: {key}，允许值: {', '.join(self.SORT_WHITELIST)}"
            )

        primary_order = self.SORT_WHITELIST[key]
        self._query = self._query.order_by(primary_order, Project.id.desc())
        self._sorted = True
        return self

    def paginate(self, page: int = 1, per_page: int = DEFAULT_PER_PAGE):
        """执行稳定分页查询（默认 12 条/页）。"""
        if not self._sorted:
            self.apply_sort(self.DEFAULT_SORT)

        safe_page = max(int(page or 1), 1)
        safe_per_page = min(max(int(per_page or self.DEFAULT_PER_PAGE), 1), 50)
        return self._query.paginate(page=safe_page, per_page=safe_per_page, error_out=False)

    def count(self) -> int:
        """返回当前筛选条件下的精确项目总数。"""
        return self._query.with_entities(func.count(Project.id)).scalar() or 0
