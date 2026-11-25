# [负责人：邓春鹏 | 核心交付 | 对接：周世航(permissions/models)、方成朋(ReviewService 职责边界)]
"""M2 项目管理、媒体安全与分类维护服务（app/services/project_service.py）

对应《非遗数字化管理平台系统分析与设计报告》：
- 业务规则：BR-01~BR-03、BR-06、BR-07、BR-10
- 接口与用例：API-10~API-15、UC-01、UC-03、图 4-3、TC-03、TC-08、TE-01、TE-02、TE-05
- 职责边界：仅负责项目 CRUD、媒体上传与读取、浏览量计数及分类维护；
  项目状态流转（submit/approve/reject/archive/restore）统一交由方成朋负责的 ReviewService。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from app import db
from app.models import (
    Category,
    Certification,
    MediaAsset,
    Project,
    ProjectDetail,
    Region,
    Tag,
)
from app.permissions import can_edit_project
from app.services.query_builder import ProjectQueryBuilder


# ----------------------------------------------------------------------
# 领域异常：由蓝图层（app/projects.py / app/admin.py）统一映射 HTTP 状态码
# ----------------------------------------------------------------------
class ServiceError(Exception):
    status_code = 400


class ValidationError(ServiceError):
    """表单字段校验失败（HTTP 400），携带逐字段错误字典（满足 3.2 易用性 & TE-01）。"""

    status_code = 400

    def __init__(self, errors: dict[str, str], message: str = "表单校验失败") -> None:
        super().__init__(message)
        self.errors = errors


class PermissionDeniedError(ServiceError):
    status_code = 403


class NotFoundError(ServiceError):
    status_code = 404


class ConflictStateError(ServiceError):
    """当前状态不允许此操作，例如归档只读（BR-06）或待审锁定（HTTP 409）。"""

    status_code = 409


class FileTooLargeError(ServiceError):
    """上传文件超过大小白名单（HTTP 413，对应 UC-01）。"""

    status_code = 413


# ----------------------------------------------------------------------
# 媒体上传安全白名单（对应 5.5 节安全与部署 & TE-02 非法文件拦截）
# ----------------------------------------------------------------------
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOC_EXTS = {".pdf"}
ALLOWED_MIME_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 单张图片上限 5 MB
MAX_PDF_BYTES = 10 * 1024 * 1024    # 单个 PDF 上限 10 MB


class ProjectService:
    """非遗项目业务与媒体管理服务。"""

    # ------------------------------------------------------------------
    # 1. 列表检索（委托 ProjectQueryBuilder）
    # ------------------------------------------------------------------
    @staticmethod
    def list_projects(
        *,
        user=None,
        scope: str = "public",
        region_id: Optional[int] = None,
        category_id: Optional[int] = None,
        tag_ids: Optional[Sequence[int]] = None,
        tag_match_mode: str = "all",
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        sort: Optional[str] = None,
        page: int = 1,
        per_page: int = 12,
    ):
        builder = (
            ProjectQueryBuilder()
            .apply_scope(user=user, scope=scope)
            .filter_status(status)
            .filter_region(region_id)
            .filter_category(category_id)
            .filter_tags(tag_ids, match_mode=tag_match_mode)
            .filter_keyword(keyword)
            .apply_sort(sort)
        )
        return builder.paginate(page=page, per_page=per_page)

    # ------------------------------------------------------------------
    # 2. 详情查看 + 同会话浏览量去重（API-11 / 图 4-3 / TE-05）
    # ------------------------------------------------------------------
    @staticmethod
    def can_view_project(user, project: Project) -> bool:
        """判断用户是否有权查看指定项目（公开项目人人可看；非公开仅作者/认证者/管理员可看）。"""
        if project.status == "deleted":
            return False
        if project.status == "published" and project.visibility == "public":
            return True
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return bool(can_edit_project(user, project))

    @classmethod
    def get_project_detail(
        cls,
        project_id: int,
        *,
        user=None,
        flask_session: Optional[dict] = None,
    ) -> Project:
        project = Project.query.filter(
            Project.id == project_id,
            Project.status != "deleted",
        ).first()
        if not project:
            raise NotFoundError("项目不存在")

        if not cls.can_view_project(user, project):
            raise PermissionDeniedError("无权查看该非公开项目")

        # 仅公开项目在“同一会话”内首次访问时浏览量 +1（图 4-3）
        is_public = project.status == "published" and project.visibility == "public"
        if is_public and flask_session is not None:
            viewed: list[int] = list(flask_session.get("viewed_projects", []))
            if project.id not in viewed:
                # 使用 SQL 原子自增，避免并发覆盖
                Project.query.filter_by(id=project.id).update(
                    {Project.views: Project.views + 1}
                )
                db.session.commit()
                viewed.append(project.id)
                flask_session["viewed_projects"] = viewed
                flask_session.modified = True
                db.session.refresh(project)

        return project

    # ------------------------------------------------------------------
    # 3. 表单校验（BR-01 & TE-01 逐字段提示）
    # ------------------------------------------------------------------
    @staticmethod
    def validate_project_payload(data: Mapping[str, Any]) -> dict[str, Any]:
        errors: dict[str, str] = {}

        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        region_id = data.get("region_id")
        category_id = data.get("category_id")
        visibility = (data.get("visibility") or "public").strip().lower()

        if not title:
            errors["title"] = "请填写项目标题"
        elif len(title) > 100:
            errors["title"] = "项目标题不能超过 100 个字符"

        if not summary:
            errors["summary"] = "请填写项目摘要"

        if not region_id or not str(region_id).isdigit():
            errors["region_id"] = "请选择所属地区"
        elif not Region.query.get(int(region_id)):
            errors["region_id"] = "所选地区不存在"

        if not category_id or not str(category_id).isdigit():
            errors["category_id"] = "请选择非遗门类"
        elif not Category.query.get(int(category_id)):
            errors["category_id"] = "所选门类不存在"

        if visibility not in {"public", "internal"}:
            errors["visibility"] = "可见性仅支持 public 或 internal"

        if errors:
            raise ValidationError(errors)

        raw_tag_ids = data.get("tag_ids") or []
        tag_ids = sorted({int(tid) for tid in raw_tag_ids if str(tid).isdigit()})

        return {
            "title": title,
            "summary": summary,
            "region_id": int(region_id),
            "category_id": int(category_id),
            "visibility": visibility,
            "content": (data.get("content") or "").strip(),
            "history": (data.get("history") or "").strip(),
            "protection": (data.get("protection") or "").strip(),
            "tag_ids": tag_ids,
        }

    # ------------------------------------------------------------------
    # 4. 新建、编辑与软删除（API-12 / API-13 / BR-02 / BR-03 / BR-06 / BR-10）
    # ------------------------------------------------------------------
    @classmethod
    def create_project(
        cls,
        user,
        data: Mapping[str, Any],
        *,
        cover_file: Optional[FileStorage] = None,
        extra_files: Optional[Sequence[FileStorage]] = None,
    ) -> Project:
        if user.role not in {"manager", "admin", "sysadmin"}:
            raise PermissionDeniedError("当前角色无权新建项目")

        cleaned = cls.validate_project_payload(data)

        # BR-03：管理员创建项目可直接发布；项目管理者创建为草稿（须提交审核）
        initial_status = "published" if user.role in {"admin", "sysadmin"} else "draft"

        project = Project(
            title=cleaned["title"],
            region_id=cleaned["region_id"],
            category_id=cleaned["category_id"],
            owner_id=user.id,
            status=initial_status,
            visibility=cleaned["visibility"],
            views=0,
        )
        if hasattr(Project, "summary"):
            project.summary = cleaned["summary"]

        if cleaned["tag_ids"]:
            project.tags = Tag.query.filter(Tag.id.in_(cleaned["tag_ids"])).all()

        db.session.add(project)
        db.session.flush()  # 获取 project.id 供 detail 和 media_asset 关联

        detail = ProjectDetail(
            project_id=project.id,
            content=cleaned["content"] or cleaned["summary"],
            history=cleaned["history"],
            protection=cleaned["protection"],
        )
        db.session.add(detail)

        # 处理媒体文件（封面 + 图集/PDF）
        if cover_file and cover_file.filename:
            cls._store_media_asset(project.id, cover_file, is_cover=True)
        for f in extra_files or []:
            if f and f.filename:
                cls._store_media_asset(project.id, f, is_cover=False)

        db.session.commit()
        return project

    @classmethod
    def update_project(
        cls,
        user,
        project_id: int,
        data: Mapping[str, Any],
        *,
        cover_file: Optional[FileStorage] = None,
        extra_files: Optional[Sequence[FileStorage]] = None,
    ) -> Project:
        project = Project.query.filter(
            Project.id == project_id,
            Project.status != "deleted",
        ).first()
        if not project:
            raise NotFoundError("项目不存在")

        if not can_edit_project(user, project):
            raise PermissionDeniedError("无权编辑该项目")

        # BR-06：归档项目只读，必须先走 ReviewService 恢复
        if project.status == "archived":
            raise ConflictStateError("项目已归档处于只读状态，请先申请修改/恢复")

        # 待审锁定：防止项目管理者在管理员审核期间篡改内容
        if project.status == "pending" and user.role == "manager":
            raise ConflictStateError("项目正在审核中，暂不可修改")

        cleaned = cls.validate_project_payload(data)

        project.title = cleaned["title"]
        project.region_id = cleaned["region_id"]
        project.category_id = cleaned["category_id"]
        project.visibility = cleaned["visibility"]
        if hasattr(Project, "summary"):
            project.summary = cleaned["summary"]
        if hasattr(Project, "updated_at"):
            project.updated_at = datetime.now(timezone.utc)

        project.tags = (
            Tag.query.filter(Tag.id.in_(cleaned["tag_ids"])).all()
            if cleaned["tag_ids"]
            else []
        )

        detail = ProjectDetail.query.filter_by(project_id=project.id).first()
        if detail is None:
            detail = ProjectDetail(project_id=project.id)
            db.session.add(detail)
        detail.content = cleaned["content"] or cleaned["summary"]
        detail.history = cleaned["history"]
        detail.protection = cleaned["protection"]

        if cover_file and cover_file.filename:
            cls._store_media_asset(project.id, cover_file, is_cover=True)
        for f in extra_files or []:
            if f and f.filename:
                cls._store_media_asset(project.id, f, is_cover=False)

        db.session.commit()
        return project

    @staticmethod
    def soft_delete_project(user, project_id: int) -> Project:
        """软删除项目（BR-10），保留硬盘媒体文件以支持审计/恢复。"""
        project = Project.query.filter(
            Project.id == project_id,
            Project.status != "deleted",
        ).first()
        if not project:
            raise NotFoundError("项目不存在")

        if not can_edit_project(user, project):
            raise PermissionDeniedError("无权删除该项目")

        # 已发布/归档项目通常仅管理员可删（对应图 4-6 状态图）
        if project.status in {"published", "archived"} and user.role == "manager":
            raise PermissionDeniedError("已发布或已归档项目仅可由管理员删除")

        project.status = "deleted"
        db.session.commit()
        return project

    # ------------------------------------------------------------------
    # 5. 媒体文件安全校验、落盘与受控读取（5.5 节 / UC-01 / TE-02）
    # ------------------------------------------------------------------
    @staticmethod
    def _get_upload_dir() -> Path:
        upload_dir = Path(
            current_app.config.get(
                "UPLOAD_FOLDER",
                os.path.join(current_app.instance_path, "uploads"),
            )
        )
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    @staticmethod
    def _validate_file_security(file: FileStorage, *, require_image: bool = False) -> str:
        """执行扩展名、MIME、大小及真实文件头四重校验，返回规范后缀。"""
        filename = (file.filename or "").strip()
        ext = Path(filename).suffix.lower()

        allowed_exts = ALLOWED_IMAGE_EXTS if require_image else (ALLOWED_IMAGE_EXTS | ALLOWED_DOC_EXTS)
        if ext not in allowed_exts:
            raise ValidationError({"media": f"不支持的文件格式: {ext or '未知'}"})

        mimetype = (file.mimetype or "").lower()
        if mimetype and mimetype not in ALLOWED_MIME_TYPES.get(ext, set()):
            raise ValidationError({"media": f"文件 MIME 类型不合法: {mimetype}"})

        # 计算文件大小（兼容未带 Content-Length 的流）
        stream = file.stream
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)

        max_bytes = MAX_IMAGE_BYTES if ext in ALLOWED_IMAGE_EXTS else MAX_PDF_BYTES
        if size == 0:
            raise ValidationError({"media": "上传文件为空"})
        if size > max_bytes:
            raise FileTooLargeError(f"文件大小超过上限（最大 {max_bytes // (1024 * 1024)} MB）")

        # 真实文件头/内容校验，防止改后缀伪造（覆盖 TE-02）
        if ext in ALLOWED_IMAGE_EXTS:
            try:
                with Image.open(stream) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError):
                raise ValidationError({"media": "图片文件已损坏或内容与扩展名不符"})
            finally:
                stream.seek(0)
        elif ext == ".pdf":
            header = stream.read(5)
            stream.seek(0)
            if header != b"%PDF-":
                raise ValidationError({"media": "PDF 文件头无效，疑似伪造文件"})

        return ext

    @classmethod
    def _store_media_asset(
        cls,
        project_id: int,
        file: FileStorage,
        *,
        is_cover: bool = False,
    ) -> MediaAsset:
        ext = cls._validate_file_security(file, require_image=is_cover)

        # 封面唯一性维护：先取消旧封面标记
        if is_cover:
            MediaAsset.query.filter_by(project_id=project_id, is_cover=True).update(
                {MediaAsset.is_cover: False}
            )

        safe_name = f"{uuid.uuid4().hex}{ext}"
        upload_dir = cls._get_upload_dir()
        target_path = upload_dir / safe_name
        file.save(target_path)

        asset = MediaAsset(
            project_id=project_id,
            path=safe_name,  # 仅存安全文件名，读取时拼接 instance/uploads/
            is_cover=is_cover,
        )
        db.session.add(asset)
        return asset

    @classmethod
    def get_authorized_media(cls, asset_id: int, user=None) -> tuple[Path, str]:
        """受控媒体读取：返回 (upload_dir, filename) 供 send_from_directory 使用。"""
        asset = MediaAsset.query.get(asset_id)
        if not asset:
            raise NotFoundError("媒体资源不存在")

        project = Project.query.get(asset.project_id)
        if not project or not cls.can_view_project(user, project):
            raise PermissionDeniedError("无权访问该媒体资源")

        return cls._get_upload_dir(), asset.path


class TaxonomyService:
    """M3 分类体系维护服务（对应 API-15：/admin/taxonomy，仅管理员/系统管理员调用）。"""

    @staticmethod
    def create_region(name: str, level: str, parent_id: Optional[int] = None) -> Region:
        name = (name or "").strip()
        if not name or len(name) > 50:
            raise ValidationError({"name": "地区名称需为 1-50 个字符"})
        if level not in {"province", "city", "county"}:
            raise ValidationError({"level": "地区层级仅支持 province/city/county"})
        if parent_id is not None and not Region.query.get(parent_id):
            raise ValidationError({"parent_id": "上级地区不存在"})

        region = Region(name=name, level=level, parent_id=parent_id)
        db.session.add(region)
        db.session.commit()
        return region

    @staticmethod
    def update_region(
        region_id: int,
        name: str,
        parent_id: Optional[int] = None,
    ) -> Region:
        region = Region.query.get(region_id)
        if not region:
            raise NotFoundError("地区不存在")

        name = (name or "").strip()
        if not name or len(name) > 50:
            raise ValidationError({"name": "地区名称需为 1-50 个字符"})

        if parent_id is not None:
            if parent_id == region_id:
                raise ConflictStateError("不能将地区设为自身的上级")
            if not Region.query.get(parent_id):
                raise ValidationError({"parent_id": "上级地区不存在"})
            descendants = ProjectQueryBuilder.get_descendant_region_ids(region_id)
            if parent_id in descendants:
                raise ConflictStateError("不能将地区移动到其下级地区之下（防止循环引用）")

        region.name = name
        region.parent_id = parent_id
        db.session.commit()
        return region

    @staticmethod
    def delete_region(region_id: int) -> None:
        region = Region.query.get(region_id)
        if not region:
            raise NotFoundError("地区不存在")

        # 防止删除含下级地区或仍被项目引用的节点
        has_children = Region.query.filter_by(parent_id=region_id).first() is not None
        if has_children:
            raise ConflictStateError("该地区下存在下级行政区，无法直接删除")

        in_use = Project.query.filter(
            Project.region_id == region_id,
            Project.status != "deleted",
        ).first() is not None
        if in_use:
            raise ConflictStateError("该地区仍有关联的非遗项目，无法删除")

        db.session.delete(region)
        db.session.commit()

    @staticmethod
    def create_category(name: str) -> Category:
        name = (name or "").strip()
        if not name or len(name) > 50:
            raise ValidationError({"name": "门类名称需为 1-50 个字符"})
        if Category.query.filter_by(name=name).first():
            raise ConflictStateError("门类名称已存在")

        category = Category(name=name)
        db.session.add(category)
        db.session.commit()
        return category

    @staticmethod
    def delete_category(category_id: int) -> None:
        category = Category.query.get(category_id)
        if not category:
            raise NotFoundError("门类不存在")
        in_use = Project.query.filter(
            Project.category_id == category_id,
            Project.status != "deleted",
        ).first() is not None
        if in_use:
            raise ConflictStateError("该门类下仍有非遗项目，无法删除")

        db.session.delete(category)
        db.session.commit()

    @staticmethod
    def create_tag(name: str) -> Tag:
        name = (name or "").strip()
        if not name or len(name) > 30:
            raise ValidationError({"name": "标签名称需为 1-30 个字符"})
        if Tag.query.filter_by(name=name).first():
            raise ConflictStateError("标签已存在")

        tag = Tag(name=name)
        db.session.add(tag)
        db.session.commit()
        return tag

    @staticmethod
    def delete_tag(tag_id: int) -> None:
        tag = Tag.query.get(tag_id)
        if not tag:
            raise NotFoundError("标签不存在")
        db.session.delete(tag)
        db.session.commit()