# [负责人：邓春鹏 | M2/M3 路由层 | 依据：《系统接口清单》V2.0 API-14~21、API-33]
"""项目 / 分类 / 媒体 蓝图（app/projects.py，V2.0 JSON API）

实现接口（前缀 /api 由应用工厂统一注册）：

======  ====  ==============================  ==============================================
编号    方法  路径                             说明
======  ====  ==============================  ==============================================
API-14  GET   /api/projects                    查询项目列表（scope/q/region/category/tag/
                                               level/status/sort/order/page/per_page）
API-15  GET   /api/projects/<id>               查看项目详情（project/detail/tags/media/
                                               review_records/permissions）
API-16  POST  /api/projects/new                新建项目（multipart）
API-17  POST  /api/projects/<id>/edit          编辑项目（multipart）
API-18  POST  /api/projects/<id>/status        状态机：submit/approve/reject/archive/
                                               restore/request_edit/delete
API-19  GET   /api/taxonomy                    公开分类字典
API-20  GET   /api/admin/taxonomy              维护用分类字典（admin）
API-21  POST  /api/admin/taxonomy              维护分类（admin，JSON）
API-33  GET   /media/<path>                    媒体读取（无 /api 前缀，独立蓝图）
======  ====  ==============================  ==============================================

约定（V2.0「接口约定」）：
- 成功一律 HTTP 200（含创建），响应 ``{"code":"OK","message":"success","data":…}``；
- 失败由统一错误处理器包裹；表单校验 400 例外地返回 ``data.errors`` 逐字段提示；
- 不渲染 HTML、不 302；未登录一律 401 JSON。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from flask import Blueprint, abort, jsonify, request, send_from_directory, session
from flask_login import current_user

from app.permissions import admin_required, login_required, role_required
from app.services.project_service import (
    ProjectService,
    TaxonomyService,
    ValidationError,
    serialize_project,
    serialize_taxonomy,
)
from app.services.query_builder import (
    DEFAULT_PER_PAGE,
    QueryPermissionError,
    QueryValidationError,
)

projects_bp = Blueprint("projects", __name__)
media_bp = Blueprint("media", __name__)

#: API-16/17 的文本字段（multipart 与 JSON 通用）
_TEXT_FIELDS = (
    "title",
    "summary",
    "region_id",
    "category_id",
    "level",
    "visibility",
    "content",
    "history",
    "inheritance",
    "protection",
    "protection_unit",
    "source_url",
    "publish",
)


# ---------------------------------------------------------------------------
# 响应与参数工具
# ---------------------------------------------------------------------------
def _ok(data: Any = None, message: str = "success"):
    """统一成功信封（V2.0：HTTP 一律 200）。"""
    return jsonify(code="OK", message=message, data=data)


def _field_errors(errors: Mapping[str, str], message: str = "表单校验失败"):
    """400 + ``data.errors``（接口约定「data.errors 例外」）。"""
    return (
        jsonify(code="BAD_REQUEST", message=message, data={"errors": dict(errors)}),
        400,
    )


def _request_data() -> dict[str, Any]:
    """兼容 JSON 与 multipart/form-data：tags 允许重复字段或逗号分隔。"""
    if request.is_json:
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}
    data: dict[str, Any] = {field: request.form.get(field) for field in _TEXT_FIELDS}
    data["tags"] = request.form.getlist("tags")
    return data


def _query_int(name: str, default: Optional[int] = None) -> Optional[int]:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip()
    if not text.isdigit():
        abort(400, description=f"参数 {name} 必须为整数")
    return int(text)


def _query_tags() -> list[str]:
    """标签参数兼容 ``?tag=a&tag=b``、``?tag=a,b`` 与 ``?tags=`` 别名。"""
    values = request.args.getlist("tag") or request.args.getlist("tags")
    tokens: list[str] = []
    for value in values:
        for part in str(value).replace("，", ",").split(","):
            part = part.strip()
            if part:
                tokens.append(part)
    return tokens


# ---------------------------------------------------------------------------
# API-14 查询项目列表
# ---------------------------------------------------------------------------
@projects_bp.get("/projects")
def list_projects():
    scope = (request.args.get("scope") or "public").strip().lower()
    # 接口约定：/api/* 未登录一律 401（scope=mine/all 需要登录态）
    if scope in {"mine", "all"} and not current_user.is_authenticated:
        abort(401, description="未登录或会话已过期，请先登录")
    try:
        pagination = ProjectService.list_projects(
            user=current_user,
            scope=scope,
            q=request.args.get("q"),
            region=request.args.get("region"),
            category=request.args.get("category"),
            tags=_query_tags(),
            tag_mode=request.args.get("tag_mode", "all"),
            level=request.args.get("level"),
            status=request.args.get("status"),
            sort=request.args.get("sort"),
            order=request.args.get("order"),
            page=_query_int("page", 1) or 1,
            per_page=_query_int("per_page", DEFAULT_PER_PAGE) or DEFAULT_PER_PAGE,
        )
    except QueryPermissionError as exc:
        abort(403, description=str(exc))
    except QueryValidationError as exc:
        abort(400, description=str(exc))

    return _ok(
        {
            "items": [serialize_project(project) for project in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
        }
    )


# ---------------------------------------------------------------------------
# API-15 查看项目详情
# ---------------------------------------------------------------------------
@projects_bp.get("/projects/<int:project_id>")
def project_detail(project_id: int):
    project = ProjectService.view_detail(
        project_id, user=current_user, flask_session=session
    )
    return _ok(ProjectService.detail_payload(project, current_user))


# ---------------------------------------------------------------------------
# API-16 新建项目
# ---------------------------------------------------------------------------
@projects_bp.post("/projects/new")
@role_required("manager", "admin", "sysadmin")
def create_project():
    try:
        project = ProjectService.create_project(
            current_user,
            _request_data(),
            cover=request.files.get("cover"),
            attachments=request.files.getlist("attachments"),
        )
    except ValidationError as exc:
        return _field_errors(exc.errors)
    return _ok({"project": serialize_project(project)})


# ---------------------------------------------------------------------------
# API-17 编辑项目
# ---------------------------------------------------------------------------
@projects_bp.post("/projects/<int:project_id>/edit")
@role_required("manager", "admin", "sysadmin")
def edit_project(project_id: int):
    try:
        project = ProjectService.update_project(
            current_user,
            project_id,
            _request_data(),
            cover=request.files.get("cover"),
            attachments=request.files.getlist("attachments"),
        )
    except ValidationError as exc:
        return _field_errors(exc.errors)
    return _ok({"project": serialize_project(project)})


# ---------------------------------------------------------------------------
# API-18 提交 / 审核 / 归档 / 删除（状态机统一入口）
# ---------------------------------------------------------------------------
@projects_bp.post("/projects/<int:project_id>/status")
@login_required
def change_project_status(project_id: int):
    data = _request_data()
    try:
        project = ProjectService.change_status(
            current_user,
            project_id,
            str(data.get("action") or ""),
            data.get("comment"),
        )
    except ValidationError as exc:
        return _field_errors(exc.errors)
    return _ok({"project": serialize_project(project)})


# ---------------------------------------------------------------------------
# API-19 / API-20 分类字典
# ---------------------------------------------------------------------------
@projects_bp.get("/taxonomy")
def taxonomy_dict():
    return _ok(serialize_taxonomy())


@projects_bp.get("/admin/taxonomy")
@admin_required
def admin_taxonomy_dict():
    return _ok(serialize_taxonomy())


# ---------------------------------------------------------------------------
# API-21 维护地区 / 门类 / 标签
# ---------------------------------------------------------------------------
@projects_bp.post("/admin/taxonomy")
@admin_required
def update_taxonomy():
    data = _request_data()
    try:
        message = TaxonomyService.apply(data)
    except ValidationError as exc:
        return _field_errors(exc.errors)
    return _ok({"message": message})


# ---------------------------------------------------------------------------
# API-33 媒体读取（独立蓝图为的是不带 /api 前缀）
# ---------------------------------------------------------------------------
@media_bp.get("/media/<path:filepath>")
def serve_media(filepath: str):
    asset = ProjectService.resolve_media(filepath, user=current_user)
    response = send_from_directory(
        ProjectService.upload_root(),
        asset.path,
        mimetype=asset.mime or "application/octet-stream",
        conditional=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response