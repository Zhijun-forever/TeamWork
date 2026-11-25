# [本地自测底座 | 合入主仓时以周世航的 models.py 为准，请核对 summary 与软删除字段]
"""核心 ORM 模型（严格对齐报告图 5-2 与表 5-2/5-3；合入主仓时与周世航核对字段）。"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash

from app import db

# M:N 项目-标签关联表（复合主键 project_id + tag_id）
project_tag = db.Table(
    "project_tag",
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    status = db.Column(db.String(20), nullable=False, default="active")

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Region(db.Model):
    __tablename__ = "region"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=True)
    level = db.Column(db.String(20), nullable=False)  # province / city / county


class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class Tag(db.Model):
    __tablename__ = "tag"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.Text, nullable=False, default="")
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    visibility = db.Column(db.String(10), nullable=False, default="public")
    views = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    archived_at = db.Column(db.DateTime, nullable=True)

    region = db.relationship("Region", lazy="joined")
    category = db.relationship("Category", lazy="joined")
    detail = db.relationship("ProjectDetail", uselist=False, backref="project", cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=project_tag, lazy="selectin")
    media_assets = db.relationship("MediaAsset", backref="project", cascade="all, delete-orphan")


class ProjectDetail(db.Model):
    __tablename__ = "project_detail"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    history = db.Column(db.Text, nullable=False, default="")
    protection = db.Column(db.Text, nullable=False, default="")


class MediaAsset(db.Model):
    __tablename__ = "media_asset"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    is_cover = db.Column(db.Boolean, nullable=False, default=False)


class Certification(db.Model):
    __tablename__ = "certification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
