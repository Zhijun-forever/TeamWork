# [负责人：邓春鹏 | M3 检索层 | 依据：《系统接口清单》V2.0 API-14 +「接口约定」排序/分页]
"""项目检索查询构建器（app/services/query_builder.py）

对应《系统接口清单.xlsx》V2.0：
- API-14 ``GET /api/projects``：请求参数 scope / q / region / category / tag / level /
  status / sort / order / page / per_page；
- 「接口约定」：
  * 分页：page 从 1，per_page 默认 12、上限 50，响应 {items,total,page,per_page}；
  * 排序：sort ∈ views/updated_at/created_at/published_at/archived_at，
    order ∈ asc/desc，默认 updated_at desc，第二排序键 id，archived_at 空值排最后，
    非法值 400，禁止拼接 SQL（白名单查表，请求值永不进入 SQL 文本）；
  * 软删除：project 用 is_deleted + deleted_at，列表默认过滤。

地区/门类/标签既接受 **名称** 也接受 **id**（API-14 备注：“region/category 传名称或 id 均可”）。
标签 M:N 用 EXISTS（``.any()``）而不是 JOIN，避免关联表把同一项目拆成多行导致翻页重复。
"""

from __future__ import annotations

from collections import deque
from typing import Final, Iterable, Optional, Sequence

from sqlalchemy import false, or_, select

from app.models import (
    CertStatus,
    Certification,
    Project,
    ProjectDetail,
    ProjectStatus,
    Region,
    Role,
    Tag,
    Visibility,
)

#: 排序键 → 列对象（严格白名单）
SORT_COLUMNS: Final[dict[str, object]] = {
    "views": Project.views,
    "updated_at": Project.updated_at,
    "created_at": Project.created_at,
    "published_at": Project.published_at,
    "archived_at": Project.archived_at,
}

#: 排序方向
SORT_ORDERS: Final[tuple[str, str]] = ("asc", "desc")

#: 分页默认值与上限（接口约定：默认 12、上限 50）
DEFAULT_PER_PAGE: Final[int] = 12
MAX_PER_PAGE: Final[int] = 50

#: 名录级别（project.level 的 CHECK 取值）
PROJECT_LEVELS: Final[tuple[str, ...]] = ("国家级", "省级", "市级", "县级")


class QueryValidationError(ValueError):
    """查询参数非法（路由层返回 400 BAD_REQUEST）。"""


class QueryPermissionError(PermissionError):
    """数据范围越权（路由层返回 403 FORBIDDEN）。"""


class ProjectQueryBuilder:
    """非遗项目链式查询构建器（Flask-SQLAlchemy）。"""

    DEFAULT_SORT: Final[str] = "updated_at"
    DEFAULT_ORDER: Final[str] = "desc"

    def __init__(self, base_query=None) -> None:
        self._query = base_query if base_query is not None else Project.query
        # 软删除统一过滤（V2.0「接口约定」：列表默认过滤）
        self._query = self._query.filter(Project.is_deleted.is_(False))
        self._sorted = False

    # ------------------------------------------------------------------
    # 1. 数据范围与状态过滤
    # ------------------------------------------------------------------
    def apply_scope(self, user=None, scope: str = "public") -> "ProjectQueryBuilder":
        """按 scope 收口数据范围。

        - ``public``：默认视图，仅 published + public（BR-07）；
        - ``mine``：本人创建，或本人「已通过」认证的项目（普通用户为空集）；
        - ``all``：管理员/系统管理员查看全部未软删除项目。
        """
        scope = (scope or "public").strip().lower()
        if scope not in {"public", "mine", "all"}:
            raise QueryValidationError(f"非法的 scope 参数: {scope}")

        if scope == "public":
            self._query = self._query.filter(
                Project.status == ProjectStatus.PUBLISHED.value,
                Project.visibility == Visibility.PUBLIC.value,
            )
            return self

        if not (user and getattr(user, "is_authenticated", False)):
            raise QueryPermissionError("未登录用户仅可浏览公开项目")

        role = getattr(user, "role", "")

        if scope == "all":
            if role not in (Role.ADMIN.value, Role.SYSADMIN.value):
                raise QueryPermissionError("仅管理员可查看全部项目")
            return self

        # scope == "mine"
        if role in (Role.ADMIN.value, Role.SYSADMIN.value):
            self._query = self._query.filter(Project.owner_id == user.id)
        elif role == Role.MANAGER.value:
            approved_ids = select(Certification.project_id).where(
                Certification.user_id == user.id,
                Certification.status == CertStatus.APPROVED.value,
            )
            self._query = self._query.filter(
                or_(Project.owner_id == user.id, Project.id.in_(approved_ids))
            )
        else:
            # 普通用户没有项目，返回空集而不是报错，便于前端统一渲染
            self._query = self._query.filter(false())

        return self

    def filter_status(self, status: Optional[str]) -> "ProjectQueryBuilder":
        """按生命周期状态过滤（draft/pending/published/rejected/archived）。"""
        if status is None or str(status).strip() == "":
            return self
        value = str(status).strip()
        allowed = {s.value for s in ProjectStatus}
        if value not in allowed:
            raise QueryValidationError(f"非法的项目状态: {value}")
        self._query = self._query.filter(Project.status == value)
        return self

    def filter_level(self, level: Optional[str]) -> "ProjectQueryBuilder":
        """按名录级别过滤（国家级/省级/市级/县级）。"""
        if level is None or str(level).strip() == "":
            return self
        value = str(level).strip()
        if value not in PROJECT_LEVELS:
            raise QueryValidationError(
                f"非法的 level 参数: {value}，允许值: {'、'.join(PROJECT_LEVELS)}"
            )
        self._query = self._query.filter(Project.level == value)
        return self

    # ------------------------------------------------------------------
    # 2. 分类体系过滤：地区级联 / 门类 / M:N 标签（支持名称或 id）
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_region_id(token: Optional[str]) -> Optional[int]:
        text = str(token).strip() if token is not None else ""
        if not text:
            return None
        if text.isdigit():
            return int(text)
        region = Region.query.filter_by(name=text).first()
        return region.id if region else -1  # -1：名称不存在的哨兵，命中空集

    @staticmethod
    def _resolve_category_id(token: Optional[str]) -> Optional[int]:
        from app.models import Category  # 局部导入，避免模块级循环

        text = str(token).strip() if token is not None else ""
        if not text:
            return None
        if text.isdigit():
            return int(text)
        category = Category.query.filter_by(name=text).first()
        return category.id if category else -1

    @staticmethod
    def get_descendant_region_ids(region_id: int) -> list[int]:
        """地区节点 + 全部下级 ID（一次查表 + 内存 BFS，规避递归 CTE 的方言差异）。"""
        rows = Region.query.with_entities(Region.id, Region.parent_id).all()
        children_map: dict[Optional[int], list[int]] = {}
        existing: set[int] = set()
        for rid, pid in rows:
            existing.add(rid)
            children_map.setdefault(pid, []).append(rid)

        if region_id not in existing:
            return []

        result: list[int] = []
        queue: deque[int] = deque([region_id])
        visited: set[int] = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            for child in children_map.get(current, []):
                if child not in visited:
                    queue.append(child)
        return result

    def filter_region(self, region: Optional[str]) -> "ProjectQueryBuilder":
        """按地区过滤：选省/市时自动包含其下级地区项目。"""
        region_id = self._resolve_region_id(region)
        if region_id is None:
            return self
        if region_id < 0:
            self._query = self._query.filter(false())
            return self
        region_ids = self.get_descendant_region_ids(region_id)
        if not region_ids:
            self._query = self._query.filter(false())
            return self
        self._query = self._query.filter(Project.region_id.in_(region_ids))
        return self

    def filter_category(self, category: Optional[str]) -> "ProjectQueryBuilder":
        """按非遗门类过滤（名称或 id）。"""
        category_id = self._resolve_category_id(category)
        if category_id is None:
            return self
        if category_id < 0:
            self._query = self._query.filter(false())
            return self
        self._query = self._query.filter(Project.category_id == category_id)
        return self

    @staticmethod
    def _resolve_tag_tokens(tokens: Sequence[str]) -> tuple[list[int], bool]:
        """把标签 token（id 或名称）解析成 id 列表；返回 (ids, 是否存在无法解析的 token)。"""
        ids: list[int] = []
        unresolved = False
        for token in tokens:
            text = str(token).strip()
            if not text:
                continue
            if text.isdigit():
                ids.append(int(text))
                continue
            tag = Tag.query.filter_by(name=text).first()
            if tag is None:
                unresolved = True
            else:
                ids.append(tag.id)
        return sorted(set(ids)), unresolved

    def filter_tags(
        self,
        tags: Optional[Sequence[str] | Iterable[str]],
        match_mode: str = "all",
    ) -> "ProjectQueryBuilder":
        """按 M:N 标签过滤：``all``（默认，交集）或 ``any``（并集）。"""
        if not tags:
            return self
        tokens = [str(t) for t in tags if str(t).strip()]
        if not tokens:
            return self

        mode = (match_mode or "all").strip().lower()
        if mode not in {"all", "any"}:
            raise QueryValidationError(f"非法的 tag_mode 参数: {mode}")

        tag_ids, unresolved = self._resolve_tag_tokens(tokens)
        if mode == "all":
            if unresolved or not tag_ids:
                self._query = self._query.filter(false())
                return self
            for tag_id in tag_ids:
                self._query = self._query.filter(Project.tags.any(Tag.id == tag_id))
            return self

        # mode == "any"
        if not tag_ids:
            self._query = self._query.filter(false())
            return self
        self._query = self._query.filter(Project.tags.any(Tag.id.in_(tag_ids)))
        return self

    # ------------------------------------------------------------------
    # 3. 关键词检索（标题 / 摘要 / 详情四段，全参数化）
    # ------------------------------------------------------------------
    @staticmethod
    def _escape_like(keyword: str) -> str:
        return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def filter_keyword(self, keyword: Optional[str]) -> "ProjectQueryBuilder":
        if not keyword or not str(keyword).strip():
            return self
        pattern = f"%{self._escape_like(str(keyword).strip())}%"
        self._query = self._query.filter(
            or_(
                Project.title.ilike(pattern, escape="\\"),
                Project.summary.ilike(pattern, escape="\\"),
                Project.detail.has(
                    or_(
                        ProjectDetail.content.ilike(pattern, escape="\\"),
                        ProjectDetail.history.ilike(pattern, escape="\\"),
                        ProjectDetail.inheritance.ilike(pattern, escape="\\"),
                        ProjectDetail.protection.ilike(pattern, escape="\\"),
                    )
                ),
            )
        )
        return self

    # ------------------------------------------------------------------
    # 4. 排序白名单 + 二级稳定排序 + 分页
    # ------------------------------------------------------------------
    def apply_sort(
        self,
        sort: Optional[str] = None,
        order: Optional[str] = None,
    ) -> "ProjectQueryBuilder":
        key = (sort or self.DEFAULT_SORT).strip()
        if key not in SORT_COLUMNS:
            raise QueryValidationError(
                f"非法的排序字段: {key}（允许 {', '.join(SORT_COLUMNS)}）"
            )

        direction = (order or self.DEFAULT_ORDER).strip().lower()
        if direction not in SORT_ORDERS:
            raise QueryValidationError(
                f"非法的排序方向: {direction}（允许 asc/desc）"
            )

        column = SORT_COLUMNS[key]
        primary = column.asc() if direction == "asc" else column.desc()
        if key == "archived_at":
            # 接口约定：archived_at 为空时排最后
            primary = primary.nullslast()
        secondary = Project.id.asc() if direction == "asc" else Project.id.desc()

        self._query = self._query.order_by(primary, secondary)
        self._sorted = True
        return self

    def paginate(self, page: int = 1, per_page: int = DEFAULT_PER_PAGE):
        if not self._sorted:
            self.apply_sort()
        safe_page = max(int(page or 1), 1)
        safe_per_page = min(max(int(per_page or DEFAULT_PER_PAGE), 1), MAX_PER_PAGE)
        return self._query.paginate(page=safe_page, per_page=safe_per_page, error_out=False)