# [负责人：邓春鹏 | 核心交付 | 对接：周世航(注册蓝图)、谭应锋(页面变量)、方成朋(状态流转)]
"""M2 & M3 蓝图路由层（app/projects.py）

对应《非遗数字化管理平台系统分析与设计报告》表 5-4 接口清单：
- API-10: GET  /projects                     项目列表/筛选/排序/分页（支持 scope=public/mine/all）
- API-11: GET  /projects/<int:project_id>    项目详情（含同会话浏览量 +1）
- API-12: GET/POST /projects/new             新建项目（含封面与附件上传）
- API-13: GET/POST /projects/<int:project_id>/edit  编辑项目
- 辅助路由: POST /projects/<int:project_id>/delete  软删除项目（BR-10）
- 辅助路由: GET  /media/<int:asset_id>              受控媒体文件读取（5.5 节安全要求）
- API-15: GET/POST /admin/taxonomy           门类/标签/地区维护（管理员/系统管理员）

设计约定：
- 蓝图只做 HTTP 参数解析、CSRF/权限装饰、异常状态码映射和模板/JSON 响应；
- 所有业务逻辑下沉至 ProjectService / ProjectQueryBuilder / TaxonomyService；
- 同时支持 Jinja2 模板渲染与 JSON 响应（当请求头 Accept 包含 application/json 或带 ?format=json），
  方便前端（谭应锋）页面联调及 pytest 自动化测试。
"""

from __future__ import annotations

from typing import Optional

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_login import current_user

from app.models import Category, Region, Tag
from app.permissions import role_required
from app.services.project_service import (
    ConflictStateError,
    FileTooLargeError,
    NotFoundError,
    PermissionDeniedError,
    ProjectService,
    ServiceError,
    TaxonomyService,
    ValidationError,
)
from app.services.query_builder import QueryPermissionError, QueryValidationError

projects_bp = Blueprint("projects", __name__)


# ----------------------------------------------------------------------
# 内部辅助函数
# ----------------------------------------------------------------------
def _wants_json() -> bool:
    """判断客户端是否期望 JSON 响应（用于接口联调与 pytest）。"""
    if request.args.get("format") == "json":
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return (
        best == "application/json"
        and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )


def _parse_optional_int(raw: Optional[str], field_name: str) -> Optional[int]:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise QueryValidationError(f"参数 {field_name} 必须为整数")


def _parse_tag_ids() -> list[int]:
    """兼容 ?tag_id=1&tag_id=2 与 ?tag_id=1,2 两种前端传参方式。"""
    raw_list = request.args.getlist("tag_id") or request.args.getlist("tag_ids")
    ids: list[int] = []
    for item in raw_list:
        for part in str(item).split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise QueryValidationError(f"非法标签 ID: {part}")
            ids.append(int(part))
    return ids


def _serialize_project_brief(project) -> dict:
    cover = next((m for m in getattr(project, "media_assets", []) if m.is_cover), None)
    return {
        "id": project.id,
        "title": project.title,
        "summary": getattr(project, "summary", ""),
        "status": project.status,
        "visibility": project.visibility,
        "views": project.views,
        "region_id": project.region_id,
        "region_name": project.region.name if getattr(project, "region", None) else None,
        "category_id": project.category_id,
        "category_name": project.category.name if getattr(project, "category", None) else None,
        "tags": [{"id": t.id, "name": t.name} for t in getattr(project, "tags", [])],
        "cover_url": url_for("projects.serve_media", asset_id=cover.id) if cover else None,
        "updated_at": project.updated_at.isoformat() if getattr(project, "updated_at", None) else None,
        "created_at": project.created_at.isoformat() if getattr(project, "created_at", None) else None,
        "archived_at": project.archived_at.isoformat() if getattr(project, "archived_at", None) else None,
    }


def _serialize_project_detail(project) -> dict:
    data = _serialize_project_brief(project)
    detail = getattr(project, "detail", None)
    data["detail"] = {
        "content": detail.content if detail else "",
        "history": detail.history if detail else "",
        "protection": detail.protection if detail else "",
    }
    data["media_assets"] = [
        {
            "id": m.id,
            "is_cover": m.is_cover,
            "url": url_for("projects.serve_media", asset_id=m.id),
        }
        for m in getattr(project, "media_assets", [])
    ]
    return data


def _load_taxonomy_options() -> dict:
    """加载筛选栏/表单所需的分类下拉选项。"""
    return {
        "regions": Region.query.order_by(Region.level.asc(), Region.id.asc()).all(),
        "categories": Category.query.order_by(Category.id.asc()).all(),
        "tags": Tag.query.order_by(Tag.id.asc()).all(),
    }


def _error_response(exc: Exception, status_code: int, *, errors: Optional[dict] = None):
    if _wants_json():
        payload = {"error": str(exc)}
        if errors:
            payload["errors"] = errors
        return jsonify(payload), status_code
    abort(status_code, description=str(exc))


# ----------------------------------------------------------------------
# API-10：项目列表 / 筛选 / 排序 / 分页
# ----------------------------------------------------------------------
@projects_bp.route("/projects", methods=["GET"])
def list_projects():
    try:
        scope = request.args.get("scope", "public")
        region_id = _parse_optional_int(request.args.get("region_id"), "region_id")
        category_id = _parse_optional_int(request.args.get("category_id"), "category_id")
        tag_ids = _parse_tag_ids()
        tag_mode = request.args.get("tag_mode", "all")
        keyword = request.args.get("q", "").strip()
        status = request.args.get("status", "").strip() or None
        sort = request.args.get("sort", "updated_at").strip()
        page = _parse_optional_int(request.args.get("page"), "page") or 1

        pagination = ProjectService.list_projects(
            user=current_user,
            scope=scope,
            region_id=region_id,
            category_id=category_id,
            tag_ids=tag_ids,
            tag_match_mode=tag_mode,
            keyword=keyword,
            status=status,
            sort=sort,
            page=page,
            per_page=12,
        )
    except QueryValidationError as exc:
        return _error_response(exc, 400)
    except QueryPermissionError as exc:
        return _error_response(exc, 403)

    if _wants_json():
        return jsonify(
            {
                "items": [_serialize_project_brief(p) for p in pagination.items],
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            }
        )

    return render_template(
        "projects/list.html",
        pagination=pagination,
        projects=pagination.items,
        filters={
            "scope": scope,
            "region_id": region_id,
            "category_id": category_id,
            "tag_ids": tag_ids,
            "tag_mode": tag_mode,
            "q": keyword,
            "status": status,
            "sort": sort,
        },
        **_load_taxonomy_options(),
    )


# ----------------------------------------------------------------------
# API-11：项目详情（含同会话浏览量去重）
# ----------------------------------------------------------------------
@projects_bp.route("/projects/<int:project_id>", methods=["GET"])
def project_detail(project_id: int):
    try:
        project = ProjectService.get_project_detail(
            project_id,
            user=current_user,
            flask_session=session,
        )
    except NotFoundError as exc:
        return _error_response(exc, 404)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)

    if _wants_json():
        return jsonify(_serialize_project_detail(project))

    return render_template("projects/detail.html", project=project)


# ----------------------------------------------------------------------
# API-12：新建项目（项目管理者 / 管理员 / 系统管理员）
# ----------------------------------------------------------------------
@projects_bp.route("/projects/new", methods=["GET", "POST"])
@role_required("manager", "admin", "sysadmin")
def create_project():
    if request.method == "GET":
        return render_template(
            "projects/form.html",
            mode="create",
            project=None,
            form_data={},
            errors={},
            **_load_taxonomy_options(),
        )

    form_data = {
        "title": request.form.get("title", ""),
        "summary": request.form.get("summary", ""),
        "region_id": request.form.get("region_id"),
        "category_id": request.form.get("category_id"),
        "visibility": request.form.get("visibility", "public"),
        "content": request.form.get("content", ""),
        "history": request.form.get("history", ""),
        "protection": request.form.get("protection", ""),
        "tag_ids": request.form.getlist("tag_ids"),
    }
    cover_file = request.files.get("cover")
    extra_files = request.files.getlist("attachments")

    try:
        project = ProjectService.create_project(
            current_user,
            form_data,
            cover_file=cover_file,
            extra_files=extra_files,
        )
    except ValidationError as exc:
        if _wants_json():
            return _error_response(exc, 400, errors=exc.errors)
        return (
            render_template(
                "projects/form.html",
                mode="create",
                project=None,
                form_data=form_data,
                errors=exc.errors,
                **_load_taxonomy_options(),
            ),
            400,
        )
    except FileTooLargeError as exc:
        return _error_response(exc, 413)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)

    if _wants_json():
        return jsonify(_serialize_project_detail(project)), 201
    return redirect(url_for("projects.project_detail", project_id=project.id))


# ----------------------------------------------------------------------
# API-13：编辑项目（认证管理者 / 管理员 / 系统管理员）
# ----------------------------------------------------------------------
@projects_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@role_required("manager", "admin", "sysadmin")
def edit_project(project_id: int):
    try:
        project = ProjectService.get_project_detail(project_id, user=current_user)
    except NotFoundError as exc:
        return _error_response(exc, 404)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)

    if request.method == "GET":
        detail = getattr(project, "detail", None)
        form_data = {
            "title": project.title,
            "summary": getattr(project, "summary", ""),
            "region_id": project.region_id,
            "category_id": project.category_id,
            "visibility": project.visibility,
            "content": detail.content if detail else "",
            "history": detail.history if detail else "",
            "protection": detail.protection if detail else "",
            "tag_ids": [str(t.id) for t in getattr(project, "tags", [])],
        }
        return render_template(
            "projects/form.html",
            mode="edit",
            project=project,
            form_data=form_data,
            errors={},
            **_load_taxonomy_options(),
        )

    form_data = {
        "title": request.form.get("title", ""),
        "summary": request.form.get("summary", ""),
        "region_id": request.form.get("region_id"),
        "category_id": request.form.get("category_id"),
        "visibility": request.form.get("visibility", "public"),
        "content": request.form.get("content", ""),
        "history": request.form.get("history", ""),
        "protection": request.form.get("protection", ""),
        "tag_ids": request.form.getlist("tag_ids"),
    }
    cover_file = request.files.get("cover")
    extra_files = request.files.getlist("attachments")

    try:
        updated = ProjectService.update_project(
            current_user,
            project_id,
            form_data,
            cover_file=cover_file,
            extra_files=extra_files,
        )
    except ValidationError as exc:
        if _wants_json():
            return _error_response(exc, 400, errors=exc.errors)
        return (
            render_template(
                "projects/form.html",
                mode="edit",
                project=project,
                form_data=form_data,
                errors=exc.errors,
                **_load_taxonomy_options(),
            ),
            400,
        )
    except ConflictStateError as exc:
        return _error_response(exc, 409)
    except FileTooLargeError as exc:
        return _error_response(exc, 413)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)
    except NotFoundError as exc:
        return _error_response(exc, 404)

    if _wants_json():
        return jsonify(_serialize_project_detail(updated))
    return redirect(url_for("projects.project_detail", project_id=updated.id))


# ----------------------------------------------------------------------
# 辅助路由：软删除项目（BR-10）
# ----------------------------------------------------------------------
@projects_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@role_required("manager", "admin", "sysadmin")
def delete_project(project_id: int):
    try:
        ProjectService.soft_delete_project(current_user, project_id)
    except NotFoundError as exc:
        return _error_response(exc, 404)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)

    if _wants_json():
        return jsonify({"deleted": True, "project_id": project_id})
    return redirect(url_for("projects.list_projects", scope="mine"))


# ----------------------------------------------------------------------
# 辅助路由：受控媒体读取（instance/uploads/ 不直接暴露在 static 下）
# ----------------------------------------------------------------------
@projects_bp.route("/media/<int:asset_id>", methods=["GET"])
def serve_media(asset_id: int):
    try:
        upload_dir, filename = ProjectService.get_authorized_media(
            asset_id, user=current_user
        )
    except NotFoundError as exc:
        return _error_response(exc, 404)
    except PermissionDeniedError as exc:
        return _error_response(exc, 403)

    return send_from_directory(upload_dir, filename, as_attachment=False)


# ----------------------------------------------------------------------
# API-15：门类 / 标签 / 地区分类维护（管理员 / 系统管理员）
# ----------------------------------------------------------------------
@projects_bp.route("/admin/taxonomy", methods=["GET", "POST"])
@role_required("admin", "sysadmin")
def manage_taxonomy():
    if request.method == "GET":
        options = _load_taxonomy_options()
        if _wants_json():
            return jsonify(
                {
                    "regions": [
                        {
                            "id": r.id,
                            "name": r.name,
                            "level": r.level,
                            "parent_id": r.parent_id,
                        }
                        for r in options["regions"]
                    ],
                    "categories": [
                        {"id": c.id, "name": c.name} for c in options["categories"]
                    ],
                    "tags": [{"id": t.id, "name": t.name} for t in options["tags"]],
                }
            )
        return render_template("admin/taxonomy.html", **options)

    entity = (request.form.get("entity") or "").strip().lower()
    action = (request.form.get("action") or "").strip().lower()

    try:
        if entity == "region":
            if action == "create":
                parent_raw = request.form.get("parent_id")
                parent_id = int(parent_raw) if parent_raw and parent_raw.isdigit() else None
                item = TaxonomyService.create_region(
                    name=request.form.get("name", ""),
                    level=request.form.get("level", ""),
                    parent_id=parent_id,
                )
                result = {"id": item.id, "name": item.name}
            elif action == "update":
                region_id = int(request.form.get("id", "0"))
                parent_raw = request.form.get("parent_id")
                parent_id = int(parent_raw) if parent_raw and parent_raw.isdigit() else None
                item = TaxonomyService.update_region(
                    region_id=region_id,
                    name=request.form.get("name", ""),
                    parent_id=parent_id,
                )
                result = {"id": item.id, "name": item.name}
            elif action == "delete":
                TaxonomyService.delete_region(int(request.form.get("id", "0")))
                result = {"deleted": True}
            else:
                raise ValidationError({"action": f"不支持的地区操作: {action}"})

        elif entity == "category":
            if action == "create":
                item = TaxonomyService.create_category(request.form.get("name", ""))
                result = {"id": item.id, "name": item.name}
            elif action == "delete":
                TaxonomyService.delete_category(int(request.form.get("id", "0")))
                result = {"deleted": True}
            else:
                raise ValidationError({"action": f"不支持的门类操作: {action}"})

        elif entity == "tag":
            if action == "create":
                item = TaxonomyService.create_tag(request.form.get("name", ""))
                result = {"id": item.id, "name": item.name}
            elif action == "delete":
                TaxonomyService.delete_tag(int(request.form.get("id", "0")))
                result = {"deleted": True}
            else:
                raise ValidationError({"action": f"不支持的标签操作: {action}"})
        else:
            raise ValidationError({"entity": f"不支持的分类实体: {entity}"})

    except ValidationError as exc:
        return _error_response(exc, 400, errors=exc.errors)
    except NotFoundError as exc:
        return _error_response(exc, 404)
    except ConflictStateError as exc:
        return _error_response(exc, 409)
    except ServiceError as exc:
        return _error_response(exc, exc.status_code)

    if _wants_json():
        return jsonify({"ok": True, "entity": entity, "action": action, "result": result})
    return redirect(url_for("projects.manage_taxonomy"))
