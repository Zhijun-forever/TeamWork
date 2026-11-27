# [负责人：周世航 | 主仓地基 | 权限控制 V2.0（JSON API 版）]
"""权限控制模块（app/permissions.py）

编写依据
--------
1. 《系统接口清单》V2.0（2026-11-27，按前端模板 API-CONTRACT.md 重构）：
   - §1 通用约定：/api/* 未登录一律 401 JSON，严禁 302 到登录页；
   - §4.15 API-15：详情接口必须返回服务端计算的 permissions 对象
     {can_edit, can_review, can_archive, can_restore, can_submit}；
   - §4.17 API-18：状态机动作权限表（submit/approve/reject/archive/restore/
     request_edit/delete 各自的角色与归属限制）；
   - §4.8/4.9 API-08/09：admin 只能建/管 user、manager；sysadmin 账号仅命令行维护。
2. 《非遗数字化管理系统分析与设计报告》代码 6-2（角色装饰器思路）与业务规则：
   - BR-04 禁止自审（管理员不能审核自己创建的项目）；
   - BR-07 非公开项目防越权（草稿/待审/驳回/内部项目仅相关人可见）；
   - BR-10 软删除（is_deleted + deleted_at，不物理删）。
3. 权限矩阵（系统接口清单.xlsx「权限矩阵」工作表）。

两层权限模型
------------
- 接口层（粗粒度）：login_required / role_required / admin_required / sysadmin_required
  装饰器，回答“这个人能不能调这个接口”。
- 对象层（细粒度）：can_xxx(user, project) 纯函数，回答“这个人能不能对这条数据做这件事”。
  返回 bool，不直接 abort——由服务层决定抛 403（越权）还是 404（防探测）还是 409（状态冲突）。
  前端只用详情接口返回的 permissions 对象显隐按钮；**动作接口仍必须服务端二次校验**，
  隐藏按钮不是安全边界（V2.0 §1）。

错误行为（V2.0 硬性规则）
------------------------
- JSON 请求（/api/* 路径、?format=json、Accept 偏好 JSON）：
  401/403 通过 abort(…, description=中文提示) 抛出，由 app/__init__.py 的统一错误
  处理器包裹成 {"code": "UNAUTHORIZED"/"FORBIDDEN", "message": …, "data": null}。
- 旧版页面路由（过渡期保留）：未登录且 auth 蓝图已合入时 302 到登录页（带 next）；
  auth 未合入时退回 401，保证集成期不炸。

兼容性说明（合入必读）
----------------------
- role_required(*roles) 与 can_edit_project(user, project) 的签名和语义与邓春鹏
  脚手架完全一致：projects.py L38 与 project_service.py L33 的现有调用零改动。
- can_edit_project 只做“身份/归属”判断；归档只读、审核中锁定等“状态冲突”由服务层
  返回 409（BR-06），不要混进本函数，否则测试期望的 409 会变成 403。
"""

from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import abort, current_app, redirect, request, url_for
from flask_login import current_user

from app.models import Certification, CertStatus, ProjectStatus

# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _json_requested() -> bool:
    """判断当前请求是否期望 JSON 响应。

    规则与 app/__init__.py 的 _wants_json() 保持一致（三选一即算）：
    1. 查询参数 ?format=json（联调通道）；
    2. 路径以 /api/ 开头（V2.0 所有业务接口）；
    3. Accept 头明确偏好 application/json。
    这里独立实现而不 import 工厂私有函数，避免循环依赖。
    """
    if request.args.get("format") == "json":
        return True
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return (
        best == "application/json"
        and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )


def _role(user) -> Optional[str]:
    """安全取角色：匿名（AnonymousUserMixin）/ None / 未登录一律返回 None。

    所有对象级校验都经由它取角色，因此匿名用户调用任何 can_xxx 都得到 False，
    不会因访问 .role 属性而抛 AttributeError。
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "role", None)


def _handle_unauthenticated():
    """未登录的统一出口（V2.0 §1：/api/* 严禁 302）。

    - JSON 请求 → 401 + 中文描述（错误处理器包成 UNAUTHORIZED 信封）；
    - 页面请求且 auth 蓝图已注册 → 302 登录页并携带 next，登录后跳回；
    - 页面请求但 auth 尚未合入 → 退回 401，避免 url_for 抛 BuildError。
    """
    if _json_requested():
        abort(401, description="未登录或会话已过期，请先登录")
    if "auth.login" in current_app.view_functions:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    abort(401, description="未登录或会话已过期，请先登录")


# ---------------------------------------------------------------------------
# 接口层装饰器
# ---------------------------------------------------------------------------


def role_required(*roles: str, message: Optional[str] = None):
    """角色装饰器：登录 + 角色白名单（报告代码 6-2 的 V2.0 版）。

    用法（与脚手架完全兼容）::

        @projects_bp.post("/projects/<int:id>/status")
        @role_required("manager", "admin", "sysadmin")
        def change_status(id): ...

    行为：
    - 未登录 → _handle_unauthenticated()（JSON 401 / 页面 302 或 401）；
    - 已登录但角色不在白名单 → 403，description 可用 message 自定义；
    - 通过 → 执行原视图。

    注意装饰器顺序：@bp.route 必须在最外层，@role_required 紧贴函数，
    否则 Flask 注册的是未包装的裸函数，权限校验会被绕过。
    """

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return _handle_unauthenticated()
            if current_user.role not in roles:
                abort(
                    403,
                    description=message or f"需要 {' / '.join(roles)} 角色才能执行此操作",
                )
            return fn(*args, **kwargs)

        return wrapper

    return deco


def login_required(fn):
    """仅要求登录（任意角色）的装饰器，V2.0 安全版。

    为什么不直接用 flask_login.login_required：
    它的未登录处理走 login_manager.unauthorized()，默认 302 到 login_view，
    对 /api/* 违反 V2.0“一律 401 JSON、严禁 302”的硬规则。
    本装饰器复用 _handle_unauthenticated()，JSON/页面两种形态都正确。
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return _handle_unauthenticated()
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """管理员及以上（admin / sysadmin）专用装饰器。

    适用：用户管理、认证审批、分类维护、工作台等（V2.0 API-07~13/20/21/23~25）。
    """
    return role_required("admin", "sysadmin")(fn)


def sysadmin_required(fn):
    """仅系统管理员（sysadmin）专用装饰器。

    适用：AI 索引重建（API-28）、运维信息（API-30）、备份下载（API-31）。
    """
    return role_required("sysadmin")(fn)


# ---------------------------------------------------------------------------
# 身份判定（对象层的基础积木）
# ---------------------------------------------------------------------------


def is_admin(user) -> bool:
    """是否管理员及以上（admin / sysadmin）。匿名返回 False。"""
    return _role(user) in ("admin", "sysadmin")


def is_manager(user) -> bool:
    """是否项目管理者（manager）。匿名返回 False。"""
    return _role(user) == "manager"


def has_approved_cert(user_id: int, project_id: int) -> bool:
    """该用户对该项目是否持有“已通过”的认证（V2.0 编辑权/申请修改权的依据）。

    注意与 Certification.has_active() 的区别：
    - has_active 含 pending + approved，用于“防重复申请”（API-11 的 409）；
    - 本函数只认 approved，用于“能不能编辑/申请修改”——待审认证不授权。
    """
    return (
        Certification.query.filter_by(
            user_id=user_id,
            project_id=project_id,
            status=CertStatus.APPROVED.value,
        ).first()
        is not None
    )


# ---------------------------------------------------------------------------
# 对象层校验：项目（V2.0 §4.15 / §4.17，权限矩阵）
# 全部返回 bool；403/404/409 的取舍由服务层决定。
# ---------------------------------------------------------------------------


def can_view_project(user, project) -> bool:
    """能否查看项目详情（BR-07 非公开防越权）。

    规则（与权限矩阵一致）：
    - 已软删除：仅管理员可见（审计/恢复场景；普通列表一律过滤）；
    - published + public + 未删除（project.is_public）：任何人含匿名；
    - 其余（草稿/待审/驳回/归档/internal）：管理员、作者本人、持已通过认证的管理者。
    """
    if project.is_deleted:
        return is_admin(user)
    if project.is_public:
        return True
    role = _role(user)
    if role in ("admin", "sysadmin"):
        return True
    if role == "manager":
        return project.owner_id == user.id or has_approved_cert(user.id, project.id)
    return False


def can_edit_project(user, project) -> bool:
    """能否编辑项目——只判“身份/归属”，与脚手架语义完全一致（兼容保证）。

    - admin / sysadmin：任意项目；
    - manager：作者本人（可改自己的草稿/驳回稿）或持该项目已通过认证；
    - 其他角色 / 匿名：False。

    状态冲突不在这里判：归档只读（BR-06）、审核中锁定由服务层返回 409，
    详见 project_service 的编辑入口。前端按钮显隐请用 project_permissions()。
    """
    role = _role(user)
    if role in ("admin", "sysadmin"):
        return True
    if role != "manager":
        return False
    return project.owner_id == user.id or has_approved_cert(user.id, project.id)


def can_review_project(user, project) -> bool:
    """能否审核（approve/reject）项目——身份层。

    BR-04 禁止自审：管理员不能审核自己创建的项目（owner_id == user.id 时 False）。
    “项目必须处于 pending”属于状态冲突（409），由服务层判断。
    """
    return is_admin(user) and project.owner_id != user.id


def can_archive_project(user, project) -> bool:
    """能否归档项目——仅管理员及以上；published→archived 的状态校验在服务层。"""
    return is_admin(user)


def can_restore_project(user, project) -> bool:
    """能否恢复归档项目——仅管理员及以上；archived→published 的状态校验在服务层。"""
    return is_admin(user)


def can_submit_project(user, project) -> bool:
    """能否提交审核（submit）——作者本人或管理员；draft/rejected→pending 在服务层。"""
    role = _role(user)
    if role in ("admin", "sysadmin"):
        return True
    return role == "manager" and project.owner_id == user.id


def can_delete_project(user, project) -> bool:
    """能否软删除项目（V2.0 §4.17 delete 行，BR-10）。

    - admin / sysadmin：任意项目（软删除，写 is_deleted + deleted_at）；
    - manager：仅本人创建且处于 draft / rejected 的项目——
      已发布项目管理者无权删，须走管理员（权限矩阵“删除项目”行）。
    这里的 status 判断属于“权限边界”而非“状态冲突”，因此放在本函数内。
    """
    role = _role(user)
    if role in ("admin", "sysadmin"):
        return True
    return (
        role == "manager"
        and project.owner_id == user.id
        and project.status in (ProjectStatus.DRAFT.value, ProjectStatus.REJECTED.value)
    )


def can_request_edit_project(user, project) -> bool:
    """能否对归档项目发起“修改申请”（request_edit，P1，V2.0 §4.17）。

    条件：manager + 持该项目已通过认证 + 项目已归档。
    申请写入 edit_request（pending），管理员审批（API-25）通过后解除只读。
    防重复申请用 EditRequest.pending_for()（服务层 409）。
    """
    return (
        is_manager(user)
        and project.status == ProjectStatus.ARCHIVED.value
        and has_approved_cert(user.id, project.id)
    )


def project_permissions(user, project) -> dict:
    """计算 V2.0 API-15 详情响应里的 permissions 对象（前端按钮显隐唯一依据）。

    返回固定五键（bool）：
    - can_edit    ：身份可编辑 且 状态允许（draft/rejected/published；
                    归档只读、审核中锁定、已删除 → False）；
    - can_review  ：管理员 且 pending 且 非本人创建（BR-04）；
    - can_archive ：管理员 且 published；
    - can_restore ：管理员 且 archived；
    - can_submit  ：作者或管理员 且 draft/rejected。

    匿名或已软删除项目 → 五键全 False。
    再次强调：本对象只服务前端体验，动作接口（API-18）必须用上面的 can_xxx
    重新校验，不能信任前端传回的任何权限标记。
    """
    keys = ("can_edit", "can_review", "can_archive", "can_restore", "can_submit")
    if _role(user) is None or project.is_deleted:
        return dict.fromkeys(keys, False)

    admin = is_admin(user)
    owner = project.owner_id == getattr(user, "id", None)
    status = project.status
    return {
        "can_edit": can_edit_project(user, project)
        and status
        in (
            ProjectStatus.DRAFT.value,
            ProjectStatus.REJECTED.value,
            ProjectStatus.PUBLISHED.value,
        ),
        "can_review": admin and status == ProjectStatus.PENDING.value and not owner,
        "can_archive": admin and status == ProjectStatus.PUBLISHED.value,
        "can_restore": admin and status == ProjectStatus.ARCHIVED.value,
        "can_submit": (owner or admin)
        and status in (ProjectStatus.DRAFT.value, ProjectStatus.REJECTED.value),
    }


# ---------------------------------------------------------------------------
# 对象层校验：用户管理（V2.0 §4.8 / §4.9，权限矩阵“用户”各行）
# ---------------------------------------------------------------------------


def can_create_role(actor, target_role: str) -> bool:
    """actor 能否创建 target_role 角色的账号（API-08）。

    - sysadmin 目标：永远 False——系统管理员只能命令行/数据库维护（V2.0 明确）；
    - sysadmin：可建 admin / manager / user；
    - admin：只能建 manager / user（不能建管理员，更不能建 sysadmin）；
    - 其他角色：False。
    公开注册（API-01）另有约束：role 只允许 user/manager，传 admin/sysadmin 一律 403。
    """
    if target_role == "sysadmin":
        return False
    role = _role(actor)
    if role == "sysadmin":
        return target_role in ("admin", "manager", "user")
    if role == "admin":
        return target_role in ("manager", "user")
    return False


def can_manage_user(actor, target_user) -> bool:
    """actor 能否编辑/禁用 target_user（API-09）。

    - 仅管理员及以上可管理用户；
    - admin 不能动 sysadmin 账号（403）；sysadmin 可管理除“命令行专属”外的一切；
    - 禁用即软删除（status=disabled + deleted_at），不提供硬删除。
    """
    if not is_admin(actor):
        return False
    if _role(target_user) == "sysadmin" and _role(actor) != "sysadmin":
        return False
    return True
