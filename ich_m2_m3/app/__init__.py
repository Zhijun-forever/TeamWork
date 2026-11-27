# [负责人：周世航 | 主仓地基 | 应用工厂：配置/扩展/蓝图注册/统一错误响应]
"""应用工厂（app/__init__.py）

职责（对应报告 代码6-1、5.5 安全与部署、《系统接口清单.xlsx》接口约定 V1.1）：
- 统一配置：SECRET_KEY 走环境变量；数据库连接串可 SQLite→MySQL 一键切换（DATABASE_URL）；
- 上传限制：单图 ≤10MB、单 PDF ≤20MB（服务层校验），请求体全局上限 25MB（Flask 层 413）；
- 扩展初始化：SQLAlchemy / Flask-Login / Flask-WTF CSRFProtect（BR-10：POST 有 CSRF）；
- 会话 Cookie：HttpOnly + SameSite=Lax（接口约定「认证方式」）；
- 蓝图注册：按模块清单注册，未交付的模块跳过并打 WARNING（集成期渐进合入，验收前须清零）；
- 统一错误响应：403/404/413/429/500 等，HTML 走 errors/ 模板（谭应锋美化），
  JSON 一律按约定 {"code", "message", "data"} 包裹；
- 中文 JSON 不转义（ensure_ascii=False），便于前端与评测查看。

合入说明：
- 本文件为主仓唯一版本，替换 ich_m2_m3 的本地自测底座；
- 队友蓝图命名约定：auth_bp / projects_bp / admin_bp / ai_bp / main_bp（见 _BLUEPRINT_SPECS）。
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import warnings
from typing import Any, Mapping, Optional

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from jinja2 import TemplateNotFound
from markupsafe import escape
from werkzeug.exceptions import HTTPException

# ---------------------------------------------------------------------------
# 扩展单例：各模块统一 `from app import db / login_manager / csrf`
# ---------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# ---------------------------------------------------------------------------
# 上传限制（《系统接口清单.xlsx》接口约定：图片 ≤10MB、PDF ≤20MB）
# 单文件精校验在 ProjectService._validate_file_security 中按类型执行；
# MAX_CONTENT_LENGTH 是请求体总闸，必须 ≥ 最大单文件 + 表单字段开销。
# ---------------------------------------------------------------------------
MAX_UPLOAD_IMAGE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PDF_BYTES = 20 * 1024 * 1024
MAX_CONTENT_LENGTH_BYTES = 25 * 1024 * 1024

# ---------------------------------------------------------------------------
# 蓝图注册清单：(模块路径, 蓝图对象名, 负责范围)
# 顺序即合入顺序；模块文件不存在 → INFO 跳过；存在但导入失败 → WARNING 跳过。
# 验收前要求：所有模块注册成功、无 WARNING。
# ---------------------------------------------------------------------------
_BLUEPRINT_SPECS: list[tuple[str, str, str, Optional[str]]] = [
    ("app.main", "main_bp", "首页 / healthz（API-21）",None),
    ("app.auth", "auth_bp", "注册/登录/退出/我的","/api"),
    ("app.projects", "projects_bp", "项目 CRUD/检索/媒体","/api"),
    ("app.admin", "admin_bp", "用户/认证/分类/运维","/api"),
    ("app.ai", "ai_bp", "AI 问答/索引重建","/api"),
]

# JSON 错误码（接口约定「统一 JSON 失败」）
_JSON_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def create_app(test_config: Optional[Mapping[str, Any]] = None) -> Flask:
    """应用工厂。test_config 为 pytest 用的覆盖配置字典（与 ich_m2_m3 测试套件签名兼容）。"""
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    upload_folder = os.path.join(app.instance_path, "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    # --- SECRET_KEY：环境变量注入（5.5 安全要求），开发兜底值仅允许 debug/测试使用 ---
    secret_key = os.environ.get("SECRET_KEY") or os.environ.get("ICH_SECRET_KEY")
    if not secret_key:
        secret_key = "dev-only-insecure-key"
        if not (app.debug or (test_config or {}).get("TESTING")):
            warnings.warn(
                "未设置 SECRET_KEY 环境变量，正在使用开发兜底值；部署/演示前必须注入！",
                stacklevel=2,
            )

    # --- 数据库：默认 instance/app.db（SQLite+WAL 见 models.py PRAGMA）；
    #     生产/课程要求换 MySQL 时仅需设置 DATABASE_URL=mysql+pymysql://... ---
    database_uri = os.environ.get("DATABASE_URL") or (
        f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
    )

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # 上传与请求体上限
        UPLOAD_FOLDER=upload_folder,
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH_BYTES,
        MAX_UPLOAD_IMAGE_BYTES=MAX_UPLOAD_IMAGE_BYTES,
        MAX_UPLOAD_PDF_BYTES=MAX_UPLOAD_PDF_BYTES,
        # 会话 Cookie 安全（接口约定「认证方式」）
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        # CSRF（BR-10）：全局启用；pytest 通过 test_config 传 WTF_CSRF_ENABLED=False 关闭
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=None,  # 会话内 token 不过期，避免长表单填写后提交 400
        # --- AI 配置（M5 rag_service 读取；密钥一律环境变量注入） ---
        DASHSCOPE_API_KEY=os.environ.get("DASHSCOPE_API_KEY", ""),
        QWEN_MODEL=os.environ.get("QWEN_MODEL", "qwen-turbo"),
        QWEN_MAX_TOKENS=400,               # 报告 2.1：max_tokens=400 控费
        SILICONFLOW_API_KEY=os.environ.get("SILICONFLOW_API_KEY", ""),
        EMBEDDING_MODEL=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3"),
        AI_DAILY_LIMIT=15,                 # BR-09：每人每天 15 次（含管理员）
        AI_TOP_K=3,                        # Top3 检索 + 引用
    )
    if test_config:
        app.config.update(test_config)

    # MySQL 连接池健壮性（SQLite 时该项被忽略也无副作用）
    if database_uri.startswith("mysql"):
        app.config.setdefault(
            "SQLALCHEMY_ENGINE_OPTIONS", {"pool_pre_ping": True, "pool_recycle": 280}
        )

    # 中文JSON直出
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # --- 扩展初始化 ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 未登录跳转目标（auth_bp 合入后生效；permissions.role_required 使用同名端点）
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录后再访问该页面"
    login_manager.login_message_category = "warning"

    @login_manager.unauthorized_handler
    def _unauthorized():
        if _wants_json():
            return jsonify(code="UNAUTHORIZED", message="未登录或会话已过期，请先登录", data=None), 401
        if "auth.login" in app.view_functions:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        # auth 蓝图尚未合入：退回 401，避免 url_for 抛 BuildError
        return jsonify(code="UNAUTHORIZED", message="未登录或会话已过期，请先登录", data=None), 401

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    _register_blueprints(app)
    _register_error_handlers(app)

    @app.get("/api/csrf")
    def api_csrf():
        return jsonify(code="OK", message="success", data={"csrf_token": generate_csrf()})

    # 开发便利：首次启动自动建表（幂等）。表结构变更后删除 instance/app.db 重建；
    # 本学期不引入 Alembic 迁移。pytest（TESTING=True）由测试夹具自行 create_all。
    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app


# ---------------------------------------------------------------------------
# 蓝图注册：渐进合入期容忍缺失模块，验收前 WARNING 必须清零
# ---------------------------------------------------------------------------
def _register_blueprints(app: Flask) -> None:
    for module_name, bp_name, scope, pre_url in _BLUEPRINT_SPECS:
        try:
            if importlib.util.find_spec(module_name) is None:
                app.logger.info("[集成] 蓝图未合入，跳过：%s（%s）", module_name, scope)
                continue
            module = importlib.import_module(module_name)
        except ImportError as exc:
            # 典型场景：projects.py 已拷入但其依赖（permissions/services）尚未合入
            app.logger.warning("[集成] %s 导入失败，跳过注册：%s", module_name, exc)
            continue

        blueprint = getattr(module, bp_name, None)
        if blueprint is None:
            app.logger.warning("[集成] %s 中未找到 %s，请核对蓝图命名约定", module_name, bp_name)
            continue

        app.register_blueprint(blueprint, url_prefix=pre_url)
        app.logger.info("[集成] 已注册蓝图 %s（%s），前缀：%s", bp_name, scope, pre_url)


# ---------------------------------------------------------------------------
# 统一错误响应：JSON 按约定包裹 {code, message, data}；HTML 走 errors/ 模板
# ---------------------------------------------------------------------------
def _wants_json() -> bool:
    """与 projects.py 的判定保持一致：?format=json、/api/* 路径或 Accept 偏好 JSON。"""
    if request.args.get("format") == "json":
        return True
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return (
        best == "application/json"
        and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )


def _fallback_html(code: int, message: str) -> str:
    """errors/ 模板缺失时的极简兜底页。"""
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>{code} - 非遗数字化管理平台</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding-top:72px;'>"
        f"<h1 style='font-size:56px;margin:0;'>{code}</h1>"
        f"<p style='color:#666;'>{escape(message)}</p>"
        "<p><a href='/projects' style='color:#0d6efd;'>返回项目库</a></p>"
        "</body></html>"
    )


def _render_error(code: int, message: str):
    if _wants_json():
        payload = {
            "code": _JSON_ERROR_CODES.get(code, "ERROR"),
            "message": message,
            "data": None,
        }
        return jsonify(payload), code
    try:
        return render_template(f"errors/{code}.html", code=code, message=message), code
    except TemplateNotFound:
        return _fallback_html(code, message), code


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        # CSRF 失败（400）给出可操作提示，方便前端联调定位
        message = exc.description or exc.name
        if exc.code == 400 and "CSRF" in str(message):
            message = "CSRF 校验失败：表单缺少 csrf_token 或会话已过期，请刷新页面重试"
        return _render_error(exc.code or 500, str(message))

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        # debug/TESTING 下 Flask 会直接抛出原始异常，便于开发定位（此处理器不拦截）
        app.logger.exception("未处理异常：%s", exc)
        return _render_error(500, "服务器内部错误，请稍后重试或联系系统管理员")
