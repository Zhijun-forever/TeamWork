# [本地自测底座 | 合入主仓时以周世航的 permissions.py 为准（完全按报告代码 6-2 编写）]
"""权限装饰器与项目级校验（按报告代码 6-2 实现；合入主仓时以周世航版本为准）。"""

from __future__ import annotations

from functools import wraps

from flask import abort
from flask_login import current_user

from app.models import Certification


def role_required(*roles: str):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def can_edit_project(user, project) -> bool:
    if user.role in ("admin", "sysadmin"):
        return True
    if user.role != "manager":
        return False
    return (
        project.owner_id == user.id
        or Certification.query.filter_by(
            user_id=user.id, project_id=project.id, status="approved"
        ).first()
        is not None
    )
