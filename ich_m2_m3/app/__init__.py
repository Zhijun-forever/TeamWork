# [本地自测底座 | 合入主仓时请勿覆盖周世航版本，只需在主仓注册 projects_bp 即可]
"""应用工厂（本地自测底座；合入组内主仓时以周世航版本为准，仅需注册 projects_bp）。"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(test_config: Optional[Mapping[str, Any]] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads"), exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-ich-secret-key"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(app.instance_path, 'app.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,  # 全局请求体上限 12MB，超限自动返回 413
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    from app.projects import projects_bp

    app.register_blueprint(projects_bp)
    return app
