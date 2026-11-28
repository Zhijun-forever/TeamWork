# [负责人：邓春鹏 | M2/M3 服务层 | 依据：《系统接口清单》V2.0 API-14~21、API-33 + 报告 BR-01~BR-10]
"""项目业务、媒体安全与分类维护服务（app/services/project_service.py）

V2.0 关键约定（与 V1.1 的差异）：
- 纯 JSON API：不返回 HTML、不 302；成功 HTTP 200（含创建）；失败由 app/__init__.py
  统一包成 ``{"code","message","data"}``，本层只负责抛 400/403/404/409/413；
- 表单校验 400 允许 ``data.errors={"字段名":"提示"}``（接口约定「data.errors 例外」）；
- 时间统一 ``YYYY-MM-DD HH:MM:SS``（空格分隔，非 ISO T），未发生的事件为 null；
- 媒体 URL = ``/media/`` + ``media_asset.path`` 相对段，如 ``/media/project/<uuid>.jpg``；
- 列表序列化用 ProjectItem（不含长文与全部图片），详情返回
  ``{project, detail, tags, media, review_records, permissions}``；
- 权限一律调用 app/permissions.py 的对象级函数（can_view/can_edit/can_review/...），
  动作接口必须服务端二次校验，不信任前端。

职责边界：本文件覆盖 项目 CRUD、检索、媒体、分类字典维护、以及 API-18 状态机
（V2.0 接口清单把状态机写在 API-18 的备注里；若后续抽离 ReviewService，只需把
``ProjectService.change_status`` 的实现搬过去，路由保持不变）。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from flask import abort, current_app
from PIL import Image, UnidentifiedImageError
from sqlalchemy import false
from werkzeug.datastructures import FileStorage

from app import db
from app.models import (
    AuditLog,
    Category,
    EditRequest,
    MediaAsset,
    MediaType,
    Project,
    ProjectDetail,
    ProjectStatus,
    Region,
    RegionLevel,
    ReviewRecord,
    Tag,
    Visibility,
    now_cn,
)
from app.permissions import (
    can_archive_project,
    can_delete_project,
    can_edit_project,
    can_request_edit_project,
    can_restore_project,
    can_review_project,
    can_submit_project,
    can_view_project,
    is_admin,
    project_permissions,
)
from app.services.query_builder import (
    MAX_PER_PAGE,
    PROJECT_LEVELS,
    ProjectQueryBuilder,
    QueryPermissionError,
    QueryValidationError,
)

# ---------------------------------------------------------------------------
# 常量：媒体白名单与上限（接口约定「文件上传」：封面 jpg/png/webp ≤10MB；PDF ≤20MB）
# ---------------------------------------------------------------------------
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
DOC_EXTS = frozenset({".pdf"})
MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
THUMBNAIL_SIZE = (400, 400)
THUMBNAIL_QUALITY = 85

TIME_FMT = "%Y-%m-%d %H:%M:%S"

#: publish 参数的真值写法
_TRUTHY = frozenset({"1", "true", "on", "yes"})


class ValidationError(Exception):
    """表单校验失败 → 路由层返回 400 且 ``data.errors`` 逐字段提示。"""

    def __init__(self, errors: Mapping[str, str], message: str = "表单校验失败") -> None:
        super().__init__(message)
        self.errors = dict(errors)


# ---------------------------------------------------------------------------
# 序列化工具
# ---------------------------------------------------------------------------
def fmt_time(value: Optional[datetime]) -> Optional[str]:
    """统一时间格式：``YYYY-MM-DD HH:MM:SS``（接口约定「时间格式」）。"""
    return value.strftime(TIME_FMT) if value else None


def region_path(region: Optional[Region]) -> tuple[Optional[str], Optional[str]]:
    """返回 (地区全路径, 省份名)，如 ("贵州省安顺市", "贵州省")。"""
    if region is None:
        return None, None
    names: list[str] = []
    node: Optional[Region] = region
    seen: set[int] = set()
    while node is not None and node.id not in seen:
        names.append(node.name)
        seen.add(node.id)
        node = node.parent
    names.reverse()
    return "".join(names), names[0] if names else None


def media_url(asset: Optional[MediaAsset]) -> Optional[str]:
    if asset is None or not asset.path:
        return None
    return f"/media/{asset.path.lstrip('/')}"


def project_cover_path(project: Project) -> Optional[str]:
    """封面相对路径：优先 media_asset.is_cover，回落 project.cover_image 冗余列。"""
    cover = next((m for m in project.media_assets if m.is_cover), None)
    if cover is not None:
        return cover.path
    return project.cover_image


def serialize_project(project: Project, *, full: bool = False) -> dict[str, Any]:
    """ProjectItem（列表、创建、编辑、状态变更的统一响应体）。"""
    region_full, province = region_path(project.region)
    cover_path = project_cover_path(project)
    owner = project.owner
    data: dict[str, Any] = {
        "id": project.id,
        "title": project.title,
        "summary": project.summary or "",
        "cover": f"/media/{cover_path.lstrip('/')}" if cover_path else None,
        "region": region_full,
        "province": province,
        "category": project.category.name if project.category else None,
        "region_id": project.region_id,
        "category_id": project.category_id,
        "level": project.level,
        "status": project.status,
        "visibility": project.visibility,
        "owner": (
            {
                "id": owner.id,
                "username": owner.username,
                "name": owner.display_name,
            }
            if owner
            else None
        ),
        "views": project.views,
        "tags": [tag.name for tag in project.tags],
        "created_at": fmt_time(project.created_at),
        "updated_at": fmt_time(project.updated_at),
    }
    if full:
        data["published_at"] = fmt_time(project.published_at)
        data["archived_at"] = fmt_time(project.archived_at)
    return data


def serialize_media(asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "url": media_url(asset),
        "type": asset.type,
        "mime": asset.mime,
        "size": asset.size,
        "is_cover": bool(asset.is_cover),
        "created_at": fmt_time(asset.created_at),
    }


def serialize_review_record(record: ReviewRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "action": record.action,
        "from_status": record.from_status,
        "to_status": record.to_status,
        "reviewer_name": record.reviewer.display_name if record.reviewer else None,
        "comment": record.comment,
        "created_at": fmt_time(record.created_at),
    }


def serialize_taxonomy() -> dict[str, Any]:
    """API-19 / API-20 的分类字典（regions 为树形 DFS 序）。"""
    return {
        "regions": [
            {
                "id": region.id,
                "name": region.name,
                "level": region.level,
                "parent_id": region.parent_id,
            }
            for region in Region.ordered_for_select()
        ],
        "categories": [
            {"id": category.id, "name": category.name, "sort_order": category.sort_order}
            for category in Category.query.order_by(Category.sort_order.asc(), Category.id.asc())
        ],
        "tags": [
            {"id": tag.id, "name": tag.name}
            for tag in Tag.query.order_by(Tag.id.asc())
        ],
    }


# ---------------------------------------------------------------------------
# 项目服务
# ---------------------------------------------------------------------------
class ProjectService:
    """非遗项目业务与媒体管理。"""

    # ==================================================================
    # 1. 读取与列表（API-14 / API-15）
    # ==================================================================
    @staticmethod
    def list_projects(
        *,
        user=None,
        scope: str = "public",
        q: Optional[str] = None,
        region: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        tag_mode: str = "all",
        level: Optional[str] = None,
        status: Optional[str] = None,
        sort: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        per_page: int = 12,
    ):
        builder = (
            ProjectQueryBuilder()
            .apply_scope(user=user, scope=scope)
            .filter_status(status)
            .filter_level(level)
            .filter_region(region)
            .filter_category(category)
            .filter_tags(tags, match_mode=tag_mode)
            .filter_keyword(q)
            .apply_sort(sort, order)
        )
        return builder.paginate(page=page, per_page=per_page)

    @staticmethod
    def get_project(project_id: int, *, include_deleted: bool = False) -> Project:
        query = Project.query.filter(Project.id == project_id)
        if not include_deleted:
            query = query.filter(Project.is_deleted.is_(False))
        project = query.first()
        if project is None:
            abort(404, description="项目不存在")
        return project

    @classmethod
    def view_detail(cls, project_id: int, user=None, flask_session=None) -> Project:
        """API-15：读取详情；公开项目同会话浏览量只 +1。"""
        project = cls.get_project(project_id, include_deleted=True)
        if not can_view_project(user, project):
            abort(403, description="无权查看该非公开项目")

        if project.is_public and flask_session is not None:
            viewed: list[int] = list(flask_session.get("viewed_projects", []))
            if project.id not in viewed:
                Project.query.filter_by(id=project.id).update(
                    {Project.views: Project.views + 1}
                )
                db.session.commit()
                viewed.append(project.id)
                flask_session["viewed_projects"] = viewed
                flask_session.modified = True
                db.session.refresh(project)
        return project

    @classmethod
    def detail_payload(cls, project: Project, user=None) -> dict[str, Any]:
        detail = project.detail
        records = (
            ReviewRecord.query.filter_by(project_id=project.id)
            .order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
            .all()
        )
        return {
            "project": serialize_project(project, full=True),
            "detail": {
                "content": detail.content if detail else "",
                "history": detail.history if detail else "",
                "inheritance": detail.inheritance if detail else "",
                "protection": detail.protection if detail else "",
                "source_url": detail.source_url if detail else None,
            },
            "tags": [tag.name for tag in project.tags],
            "media": [serialize_media(asset) for asset in project.media_assets],
            "review_records": [serialize_review_record(r) for r in records],
            "permissions": project_permissions(user, project),
        }

    # ==================================================================
    # 2. 表单校验（BR-01；对齐 API-16/17 的请求字段与示例错误文案）
    # ==================================================================
    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def validate_payload(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        errors: dict[str, str] = {}

        title = cls._clean_text(data.get("title"))
        summary = cls._clean_text(data.get("summary"))
        region_raw = cls._clean_text(data.get("region_id"))
        category_raw = cls._clean_text(data.get("category_id"))
        level = cls._clean_text(data.get("level"))
        visibility = cls._clean_text(data.get("visibility")) or Visibility.PUBLIC.value
        source_url = cls._clean_text(data.get("source_url"))

        if not title:
            errors["title"] = "请填写项目标题"
        elif len(title) > 100:
            errors["title"] = "项目标题不能超过 100 个字符"

        if not summary:
            errors["summary"] = "请填写项目摘要"
        elif len(summary) > 300:
            errors["summary"] = "项目摘要不能超过 300 个字符"

        region_id = int(region_raw) if region_raw.isdigit() else None
        if region_id is None:
            errors["region_id"] = "请选择所属地区"
        elif db.session.get(Region, region_id) is None:
            errors["region_id"] = "所选地区不存在"

        category_id = int(category_raw) if category_raw.isdigit() else None
        if category_id is None:
            errors["category_id"] = "请选择非遗门类"
        elif db.session.get(Category, category_id) is None:
            errors["category_id"] = "所选门类不存在"

        if level and level not in PROJECT_LEVELS:
            errors["level"] = f"级别仅支持：{'、'.join(PROJECT_LEVELS)}"

        if visibility not in {Visibility.PUBLIC.value, Visibility.INTERNAL.value}:
            errors["visibility"] = "可见性仅支持 public 或 internal"

        if source_url:
            if len(source_url) > 500:
                errors["source_url"] = "来源链接不能超过 500 个字符"
            elif not source_url.startswith(("http://", "https://")):
                errors["source_url"] = "来源链接需以 http:// 或 https:// 开头"

        raw_tags = data.get("tags")
        tag_names: list[str] = []
        if raw_tags:
            items = raw_tags if isinstance(raw_tags, (list, tuple, set)) else [raw_tags]
            for item in items:
                for part in str(item).replace("，", ",").split(","):
                    name = part.strip()
                    if not name:
                        continue
                    if len(name) > 30:
                        errors["tags"] = "标签名称不能超过 30 个字符"
                        break
                    if name not in tag_names:
                        tag_names.append(name)

        if errors:
            raise ValidationError(errors)

        # 注：V2.0 API-16 请求里的 protection_unit 在《数据库表设计》V1.1 十四表中没有对应列
        # （《系统接口清单》标注为「待决事项②」），故本期只接收、不落库；
        # 若后续定表新增列，在此读取并写入 ProjectDetail 即可，接口字段无需变动。
        return {
            "title": title,
            "summary": summary,
            "region_id": int(region_id),
            "category_id": int(category_id),
            "level": level or None,
            "visibility": visibility,
            "content": cls._clean_text(data.get("content")),
            "history": cls._clean_text(data.get("history")),
            "inheritance": cls._clean_text(data.get("inheritance")),
            "protection": cls._clean_text(data.get("protection")),
            "source_url": source_url or None,
            "tag_names": tag_names,
        }

    @staticmethod
    def _resolve_tags(names: Sequence[str]) -> list[Tag]:
        """按名称取标签；不存在则创建（标签是自由词表，接口约定 tags 传名称）。"""
        tags: list[Tag] = []
        for name in names:
            tag = Tag.query.filter_by(name=name).first()
            if tag is None:
                tag = Tag(name=name)
                db.session.add(tag)
                db.session.flush()
            tags.append(tag)
        return tags

    # ==================================================================
    # 3. 新建 / 编辑（API-16 / API-17）
    # ==================================================================
    @staticmethod
    def _initial_status(user, publish_raw: Any) -> str:
        """V2.0：manager→draft；admin/sysadmin 默认 published（publish=0 可存草稿）。"""
        if getattr(user, "role", "") in ("admin", "sysadmin"):
            if publish_raw is None:
                return ProjectStatus.PUBLISHED.value
            return (
                ProjectStatus.PUBLISHED.value
                if str(publish_raw).strip().lower() in _TRUTHY
                else ProjectStatus.DRAFT.value
            )
        return ProjectStatus.DRAFT.value

    @classmethod
    def create_project(
        cls,
        user,
        data: Mapping[str, Any],
        *,
        cover: Optional[FileStorage] = None,
        attachments: Optional[Sequence[FileStorage]] = None,
    ) -> Project:
        cleaned = cls.validate_payload(data)
        cls._validate_media_batch(cover, attachments)

        status = cls._initial_status(user, data.get("publish"))
        project = Project(
            title=cleaned["title"],
            summary=cleaned["summary"],
            region_id=cleaned["region_id"],
            category_id=cleaned["category_id"],
            level=cleaned["level"],
            visibility=cleaned["visibility"],
            owner_id=user.id,
            status=status,
            views=0,
            published_at=now_cn() if status == ProjectStatus.PUBLISHED.value else None,
        )
        project.tags = cls._resolve_tags(cleaned["tag_names"])

        db.session.add(project)
        db.session.flush()  # 取得 project.id 供详情与媒体关联

        db.session.add(
            ProjectDetail(
                project_id=project.id,
                content=cleaned["content"] or cleaned["summary"],
                history=cleaned["history"],
                inheritance=cleaned["inheritance"],
                protection=cleaned["protection"],
                source_url=cleaned["source_url"],
            )
        )

        if cover and cover.filename:
            cls._store_media(project, cover, is_cover=True, user=user)
        for file in attachments or []:
            if file and file.filename:
                cls._store_media(project, file, is_cover=False, user=user)

        AuditLog.record(
            "create",
            user_id=user.id,
            target_type="project",
            target_id=project.id,
            detail=f"title={project.title};status={project.status}",
        )
        db.session.commit()
        return project

    @classmethod
    def update_project(
        cls,
        user,
        project_id: int,
        data: Mapping[str, Any],
        *,
        cover: Optional[FileStorage] = None,
        attachments: Optional[Sequence[FileStorage]] = None,
    ) -> Project:
        project = cls.get_project(project_id)

        if not can_edit_project(user, project):
            abort(403, description="无权编辑该项目")

        # BR-06：归档只读；待审锁定（管理者不能改审核中的稿子）
        if project.status == ProjectStatus.ARCHIVED.value:
            abort(409, description="项目已归档处于只读状态，请先恢复或申请修改")
        if project.status == ProjectStatus.PENDING.value and getattr(user, "role", "") == "manager":
            abort(409, description="项目正在审核中，暂不可修改")

        cleaned = cls.validate_payload(data)
        cls._validate_media_batch(cover, attachments)

        project.title = cleaned["title"]
        project.summary = cleaned["summary"]
        project.region_id = cleaned["region_id"]
        project.category_id = cleaned["category_id"]
        project.level = cleaned["level"]
        project.visibility = cleaned["visibility"]
        project.updated_at = now_cn()
        project.tags = cls._resolve_tags(cleaned["tag_names"])

        detail = project.detail
        if detail is None:
            detail = ProjectDetail(project_id=project.id)
            db.session.add(detail)
        detail.content = cleaned["content"] or cleaned["summary"]
        detail.history = cleaned["history"]
        detail.inheritance = cleaned["inheritance"]
        detail.protection = cleaned["protection"]
        detail.source_url = cleaned["source_url"]
        detail.updated_at = now_cn()

        if cover and cover.filename:
            cls._store_media(project, cover, is_cover=True, user=user)
        for file in attachments or []:
            if file and file.filename:
                cls._store_media(project, file, is_cover=False, user=user)

        AuditLog.record(
            "update",
            user_id=user.id,
            target_type="project",
            target_id=project.id,
            detail=f"title={project.title}",
        )
        db.session.commit()
        return project

    # ==================================================================
    # 4. 状态机（API-18：submit/approve/reject/archive/restore/request_edit/delete）
    # ==================================================================
    CLIENT_ACTIONS = (
        "submit",
        "approve",
        "reject",
        "archive",
        "restore",
        "request_edit",
        "delete",
    )

    @classmethod
    def change_status(
        cls,
        user,
        project_id: int,
        action: str,
        comment: Optional[str] = None,
    ) -> Project:
        action = (action or "").strip().lower()
        if action not in cls.CLIENT_ACTIONS:
            raise ValidationError(
                {"action": f"不支持的 action: {action or '(空)'}（允许 {', '.join(cls.CLIENT_ACTIONS)}）"}
            )

        project = cls.get_project(project_id, include_deleted=True)
        before = project.status
        comment = cls._clean_text(comment) or None

        if action == "submit":
            if not can_submit_project(user, project):
                abort(403, description="仅作者本人或管理员可提交审核")
            if before not in (ProjectStatus.DRAFT.value, ProjectStatus.REJECTED.value):
                abort(409, description="仅草稿或已驳回项目可提交审核")
            project.status = ProjectStatus.PENDING.value

        elif action in ("approve", "reject"):
            if not is_admin(user):
                abort(403, description="仅管理员可审核项目")
            if project.owner_id == user.id:
                abort(403, description="不能审核自己创建的项目")  # BR-04 禁止自审
            if before != ProjectStatus.PENDING.value:
                abort(409, description="仅待审核项目可执行该操作")
            if action == "reject" and not comment:
                raise ValidationError({"comment": "驳回必须填写审核意见"})  # BR-05
            if action == "approve":
                project.status = ProjectStatus.PUBLISHED.value
                project.published_at = project.published_at or now_cn()
            else:
                project.status = ProjectStatus.REJECTED.value

        elif action == "archive":
            if not can_archive_project(user, project):
                abort(403, description="仅管理员可归档项目")
            if before != ProjectStatus.PUBLISHED.value:
                abort(409, description="仅已发布项目可归档")
            project.status = ProjectStatus.ARCHIVED.value
            project.archived_at = now_cn()

        elif action == "restore":
            if not can_restore_project(user, project):
                abort(403, description="仅管理员可恢复项目")
            if before != ProjectStatus.ARCHIVED.value:
                abort(409, description="仅已归档项目可恢复")
            project.status = ProjectStatus.PUBLISHED.value
            project.archived_at = None
            project.published_at = project.published_at or now_cn()

        elif action == "request_edit":
            if not can_request_edit_project(user, project):
                abort(403, description="仅该项目已认证的管理者可申请修改归档项目")
            if EditRequest.pending_for(project.id) is not None:
                abort(409, description="该项目的修改申请正在审核中")
            db.session.add(
                EditRequest(
                    project_id=project.id,
                    requester_id=user.id,
                    reason=comment or "申请修改归档项目",
                )
            )

        else:  # delete
            if not can_delete_project(user, project):
                abort(403, description="无权删除该项目")
            project.soft_delete()

        if action != "request_edit":
            db.session.add(
                ReviewRecord(
                    project_id=project.id,
                    action=action,
                    from_status=before,
                    to_status=project.status,
                    reviewer_id=user.id,
                    comment=comment,
                )
            )

        AuditLog.record(
            action,
            user_id=user.id,
            target_type="project",
            target_id=project.id,
            detail=f"{before}->{project.status}" + (f";{comment}" if comment else ""),
        )
        db.session.commit()
        return project

    # ==================================================================
    # 5. 媒体：校验 → 落盘（project/<uuid>.ext）→ 缩略图 → media_asset
    # ==================================================================
    @staticmethod
    def upload_root() -> Path:
        root = Path(
            current_app.config.get(
                "UPLOAD_FOLDER", os.path.join(current_app.instance_path, "uploads")
            )
        )
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _validate_file(cls, file: FileStorage, *, require_image: bool = False) -> tuple[str, int, str]:
        """扩展名白名单 → MIME 白名单 → 大小上限 → 真实文件头校验。"""
        filename = (file.filename or "").strip()
        ext = Path(filename).suffix.lower()
        allowed = IMAGE_EXTS if require_image else (IMAGE_EXTS | DOC_EXTS)
        if ext not in allowed:
            raise ValidationError({"media": f"不支持的文件格式: {ext or '未知'}"})

        mimetype = (file.mimetype or "").lower()
        expected = MIME_BY_EXT[ext]
        if mimetype and mimetype not in (expected, "application/octet-stream"):
            raise ValidationError({"media": f"文件 MIME 类型不合法: {mimetype}"})

        stream = file.stream
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)

        max_bytes = MAX_IMAGE_BYTES if ext in IMAGE_EXTS else MAX_PDF_BYTES
        if size == 0:
            raise ValidationError({"media": "上传文件为空"})
        if size > max_bytes:
            abort(
                413,
                description=f"文件大小超过上限（最大 {max_bytes // (1024 * 1024)} MB）",
            )

        if ext in IMAGE_EXTS:
            try:
                with Image.open(stream) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError):
                raise ValidationError({"media": "图片文件已损坏或内容与扩展名不符"})
            finally:
                stream.seek(0)
        else:
            header = stream.read(5)
            stream.seek(0)
            if header != b"%PDF-":
                raise ValidationError({"media": "PDF 文件头无效，疑似伪造文件"})

        return ext, size, expected

    @classmethod
    def _validate_media_batch(
        cls,
        cover: Optional[FileStorage],
        attachments: Optional[Sequence[FileStorage]],
    ) -> None:
        """落盘前批量校验，避免第 2 个文件非法时第 1 个已写成孤儿文件。"""
        if cover and cover.filename:
            cls._validate_file(cover, require_image=True)
        for file in attachments or []:
            if file and file.filename:
                cls._validate_file(file, require_image=False)

    @classmethod
    def _store_media(
        cls,
        project: Project,
        file: FileStorage,
        *,
        is_cover: bool,
        user,
    ) -> MediaAsset:
        ext, size, mimetype = cls._validate_file(file, require_image=is_cover)

        if is_cover:
            MediaAsset.query.filter_by(project_id=project.id, is_cover=True).update(
                {MediaAsset.is_cover: False}
            )

        rel_dir = "project"
        filename = f"{uuid.uuid4().hex}{ext}"
        rel_path = f"{rel_dir}/{filename}"
        target_dir = cls.upload_root() / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        file.save(target)

        if ext in IMAGE_EXTS:
            cls._make_thumbnail(target)

        asset = MediaAsset(
            project_id=project.id,
            type=MediaType.IMAGE.value if ext in IMAGE_EXTS else MediaType.DOCUMENT.value,
            path=rel_path,
            mime=mimetype,
            size=size,
            is_cover=is_cover,
            uploaded_by=getattr(user, "id", None),
        )
        db.session.add(asset)
        if is_cover:
            project.cover_image = rel_path
        return asset

    @staticmethod
    def _make_thumbnail(path: Path) -> Optional[Path]:
        """Pillow 400px 缩略图，文件名约定 ``<uuid>_thumb.jpg``（与原图同目录）。"""
        thumb = path.with_name(f"{path.stem}_thumb.jpg")
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail(THUMBNAIL_SIZE)
                image.save(thumb, format="JPEG", quality=THUMBNAIL_QUALITY)
            return thumb
        except (UnidentifiedImageError, OSError) as exc:  # pragma: no cover - 兜底
            current_app.logger.warning("缩略图生成失败 %s: %s", path.name, exc)
            return None

    @staticmethod
    def resolve_media(filepath: str, user=None) -> MediaAsset:
        """API-33：按 ``media_asset.path`` 找资源并校验可见性（无权一律 404，防探测）。"""
        normalized = (filepath or "").replace("\\", "/").lstrip("/")
        asset = MediaAsset.query.filter_by(path=normalized).first()
        if asset is None:
            abort(404, description="文件不存在")
        project = db.session.get(Project, asset.project_id)
        if project is None or not can_view_project(user, project):
            abort(404, description="文件不存在")
        return asset


# ---------------------------------------------------------------------------
# 分类维护服务（API-21；API-19/20 的读取见 serialize_taxonomy）
# ---------------------------------------------------------------------------
class TaxonomyService:
    """地区 / 门类 / 标签维护（被引用禁止删除、地区防环）。"""

    TYPES = ("region", "category", "tag")
    ACTIONS = ("create", "update", "delete")

    # ---------------- 地区 ----------------
    @staticmethod
    def _region_name(raw: Any) -> str:
        name = str(raw or "").strip()
        if not name:
            raise ValidationError({"name": "请填写地区名称"})
        if len(name) > 50:
            raise ValidationError({"name": "地区名称不能超过 50 个字符"})
        return name

    @classmethod
    def create_region(cls, data: Mapping[str, Any]) -> str:
        name = cls._region_name(data.get("name"))
        level = str(data.get("level") or "").strip()
        if level not in {item.value for item in RegionLevel}:
            raise ValidationError({"level": "地区层级仅支持 province/city/county"})

        parent_id = cls._optional_int(data.get("parent_id"), "parent_id")
        if parent_id is not None and db.session.get(Region, parent_id) is None:
            raise ValidationError({"parent_id": "上级地区不存在"})

        db.session.add(
            Region(
                name=name,
                level=level,
                parent_id=parent_id,
                code=cls._optional_text(data.get("code"), 20),
                sort_order=cls._optional_int(data.get("sort_order"), "sort_order") or 0,
            )
        )
        AuditLog.record("create", target_type="taxonomy", detail=f"region={name}")
        db.session.commit()
        return "已创建"

    @classmethod
    def update_region(cls, region_id: int, data: Mapping[str, Any]) -> str:
        region = db.session.get(Region, region_id)
        if region is None:
            abort(404, description="地区不存在")

        if data.get("name") is not None:
            region.name = cls._region_name(data.get("name"))
        if data.get("level") is not None:
            level = str(data.get("level")).strip()
            if level not in {item.value for item in RegionLevel}:
                raise ValidationError({"level": "地区层级仅支持 province/city/county"})
            if region.children and level != region.level:
                abort(409, description="该地区存在下级节点，不能修改层级")
            region.level = level
        if "parent_id" in data:
            parent_id = cls._optional_int(data.get("parent_id"), "parent_id")
            if parent_id is not None:
                if parent_id == region.id:
                    abort(409, description="不能将地区设为自身的上级")
                if db.session.get(Region, parent_id) is None:
                    raise ValidationError({"parent_id": "上级地区不存在"})
                if parent_id in ProjectQueryBuilder.get_descendant_region_ids(region.id):
                    abort(409, description="不能将地区移动到其下级地区之下")
            region.parent_id = parent_id
        if data.get("code") is not None:
            region.code = cls._optional_text(data.get("code"), 20)
        if data.get("sort_order") is not None:
            region.sort_order = cls._optional_int(data.get("sort_order"), "sort_order") or 0

        AuditLog.record("update", target_type="taxonomy", detail=f"region={region.name}")
        db.session.commit()
        return "已更新"

    @classmethod
    def delete_region(cls, region_id: int) -> str:
        region = db.session.get(Region, region_id)
        if region is None:
            abort(404, description="地区不存在")
        if region.children:
            abort(409, description="该地区下存在下级行政区，无法直接删除")
        if Project.query.filter(
            Project.region_id == region.id, Project.is_deleted.is_(False)
        ).first():
            abort(409, description="该地区仍有关联的非遗项目，无法删除")

        AuditLog.record("delete", target_type="taxonomy", detail=f"region={region.name}")
        db.session.delete(region)
        db.session.commit()
        return "已删除"

    # ---------------- 门类 ----------------
    @staticmethod
    def _category_name(raw: Any) -> str:
        name = str(raw or "").strip()
        if not name:
            raise ValidationError({"name": "请填写门类名称"})
        if len(name) > 50:
            raise ValidationError({"name": "门类名称不能超过 50 个字符"})
        return name

    @classmethod
    def create_category(cls, data: Mapping[str, Any]) -> str:
        name = cls._category_name(data.get("name"))
        if Category.query.filter_by(name=name).first():
            abort(409, description="门类名称已存在")
        db.session.add(
            Category(
                name=name,
                code=cls._optional_text(data.get("code"), 20),
                description=cls._optional_text(data.get("description"), 2000),
                sort_order=cls._optional_int(data.get("sort_order"), "sort_order") or 0,
            )
        )
        AuditLog.record("create", target_type="taxonomy", detail=f"category={name}")
        db.session.commit()
        return "已创建"

    @classmethod
    def update_category(cls, category_id: int, data: Mapping[str, Any]) -> str:
        category = db.session.get(Category, category_id)
        if category is None:
            abort(404, description="门类不存在")
        if data.get("name") is not None:
            name = cls._category_name(data.get("name"))
            if Category.query.filter(
                Category.name == name, Category.id != category.id
            ).first():
                abort(409, description="门类名称已存在")
            category.name = name
        if data.get("code") is not None:
            category.code = cls._optional_text(data.get("code"), 20)
        if data.get("description") is not None:
            category.description = cls._optional_text(data.get("description"), 2000)
        if data.get("sort_order") is not None:
            category.sort_order = cls._optional_int(data.get("sort_order"), "sort_order") or 0

        AuditLog.record("update", target_type="taxonomy", detail=f"category={category.name}")
        db.session.commit()
        return "已更新"

    @classmethod
    def delete_category(cls, category_id: int) -> str:
        category = db.session.get(Category, category_id)
        if category is None:
            abort(404, description="门类不存在")
        if Project.query.filter(
            Project.category_id == category.id, Project.is_deleted.is_(False)
        ).first():
            abort(409, description="该门类下仍有非遗项目，无法删除")

        AuditLog.record("delete", target_type="taxonomy", detail=f"category={category.name}")
        db.session.delete(category)
        db.session.commit()
        return "已删除"

    # ---------------- 标签 ----------------
    @staticmethod
    def _tag_name(raw: Any) -> str:
        name = str(raw or "").strip()
        if not name:
            raise ValidationError({"name": "请填写标签名称"})
        if len(name) > 30:
            raise ValidationError({"name": "标签名称不能超过 30 个字符"})
        return name

    @classmethod
    def create_tag(cls, data: Mapping[str, Any]) -> str:
        name = cls._tag_name(data.get("name"))
        if Tag.query.filter_by(name=name).first():
            abort(409, description="标签已存在")
        db.session.add(Tag(name=name))
        AuditLog.record("create", target_type="taxonomy", detail=f"tag={name}")
        db.session.commit()
        return "已创建"

    @classmethod
    def update_tag(cls, tag_id: int, data: Mapping[str, Any]) -> str:
        tag = db.session.get(Tag, tag_id)
        if tag is None:
            abort(404, description="标签不存在")
        name = cls._tag_name(data.get("name"))
        if Tag.query.filter(Tag.name == name, Tag.id != tag.id).first():
            abort(409, description="标签已存在")
        tag.name = name
        AuditLog.record("update", target_type="taxonomy", detail=f"tag={name}")
        db.session.commit()
        return "已更新"

    @classmethod
    def delete_tag(cls, tag_id: int) -> str:
        from app.models import project_tag

        tag = db.session.get(Tag, tag_id)
        if tag is None:
            abort(404, description="标签不存在")
        db.session.execute(project_tag.delete().where(project_tag.c.tag_id == tag.id))
        AuditLog.record("delete", target_type="taxonomy", detail=f"tag={tag.name}")
        db.session.delete(tag)
        db.session.commit()
        return "已删除"

    # ---------------- 分发 ----------------
    @classmethod
    def apply(cls, data: Mapping[str, Any]) -> str:
        """按 ``type`` + ``action`` 分发（API-21）。"""
        entity = str(data.get("type") or "").strip().lower()
        action = str(data.get("action") or "").strip().lower()

        if entity not in cls.TYPES:
            raise ValidationError({"type": f"type 仅支持 {' / '.join(cls.TYPES)}"})
        if action not in cls.ACTIONS:
            raise ValidationError({"action": f"action 仅支持 {' / '.join(cls.ACTIONS)}"})

        if action == "create":
            if entity == "region":
                return cls.create_region(data)
            if entity == "category":
                return cls.create_category(data)
            return cls.create_tag(data)

        target_id = cls._optional_int(data.get("id"), "id")
        if target_id is None:
            raise ValidationError({"id": "缺少必填参数 id"})

        if action == "update":
            if entity == "region":
                return cls.update_region(target_id, data)
            if entity == "category":
                return cls.update_category(target_id, data)
            return cls.update_tag(target_id, data)

        if entity == "region":
            return cls.delete_region(target_id)
        if entity == "category":
            return cls.delete_category(target_id)
        return cls.delete_tag(target_id)

    # ---------------- 工具 ----------------
    @staticmethod
    def _optional_int(raw: Any, field: str) -> Optional[int]:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if not text.lstrip("-").isdigit():
            raise ValidationError({field: f"参数 {field} 必须为整数"})
        return int(text)

    @staticmethod
    def _optional_text(raw: Any, limit: int) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip()
        return text[:limit] or None