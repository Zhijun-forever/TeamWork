# [负责人：周世航 | 主仓地基 | 依据：《数据库表设计.xlsx》V1.1 + 报告图5-2/表5-2/5-3]
"""全量 14 张表 ORM 模型（app/models.py）

严格对齐《数据库表设计.xlsx》V1.1：
- 「字段明细」：14 张表逐列实现（VARCHAR→String、TEXT→Text、BLOB→LargeBinary）；
- 「关系与完整性」：外键显式声明；project_detail 1:1（UNIQUE）；project_tag M:N 复合主键；
  region 自关联树；审核记录/审计日志只增不改；
- 「索引建议」：project 5 索引、certification 复合索引、knowledge_chunk (project_id, chunk_no)
  唯一约束、chat_log (user_id, created_at)、audit_log (created_at)。
  注意：ux_cert_active / ux_edit_pending 是“条件唯一索引”，MySQL 不支持 partial index，
  为保证 SQLite/MySQL 双兼容，改由服务层（application-level）校验，此处仅建普通复合索引，
  并提供 has_active() / pending_for() 辅助方法供服务层调用。

全局约定（2026-11-26 定稿，全员遵守）：
1. 软删除：project 用 is_deleted + deleted_at（不使用 status='deleted'！status 的 CHECK
   约束只允许 draft/pending/published/rejected/archived）。M2/M3 合入代码需同步修改过滤条件。
2. 时间：统一 Asia/Shanghai（UTC+8 固定偏移，无夏令时），以 naive datetime 存储，
   保证 SQLite/MySQL 兼容；展示层不做二次转换。
3. 状态：VARCHAR + CheckConstraint（SQLite 会在运行时强制校验）。
4. SQLite 需显式开启外键约束与 WAL（见下方 Engine connect 事件监听）。
"""

from __future__ import annotations

import sqlite3
from array import array
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Sequence

from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

# ---------------------------------------------------------------------------
# 时间基准：Asia/Shanghai（UTC+8），naive datetime 存库
# ---------------------------------------------------------------------------
CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    """统一时间戳：东八区当前时间（naive，直接可存 SQLite/MySQL）。"""
    return datetime.now(CN_TZ).replace(tzinfo=None)


def today_start_cn() -> datetime:
    """今日 00:00:00（东八区），供 ChatLog 当日限流计数使用。"""
    return now_cn().replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# SQLite 运行时 PRAGMA：外键强制 + WAL（报告 1.3：SQLite3(WAL)）
# 仅对 SQLite 连接生效；换 MySQL 连接串时无副作用
# ---------------------------------------------------------------------------
@event.listens_for(Engine, "connect")
def _sqlite_runtime_pragmas(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")   # SQLite 默认不强制外键，必须显式开启
        cursor.execute("PRAGMA journal_mode=WAL")   # 演示时读写并发更稳
        cursor.close()


# ---------------------------------------------------------------------------
# 枚举（报告图 4-5：Role / ProjectStatus / Visibility / CertStatus 等）
# 继承 str：蓝图/服务层可直接与普通字符串比较，如 user.role == Role.ADMIN
# ---------------------------------------------------------------------------
class Role(str, Enum):
    SYSADMIN = "sysadmin"   # 系统管理员：运维、账号兜底、日志备份
    ADMIN = "admin"         # 管理员：审核发布、归档、用户/分类管理
    MANAGER = "manager"     # 项目管理者：维护自己认证的项目
    USER = "user"           # 普通用户：浏览公开项目、提问


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"   # 禁用即软删除（API-06：不提供硬删除）
    DELETED = "deleted"     # 用户主动注销（软删除并匿名化）


class RegionLevel(str, Enum):
    PROVINCE = "province"
    CITY = "city"
    COUNTY = "county"


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Visibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"


class ProjectLevel(str, Enum):
    """名录级别（可选字段，与生命周期 status 无关）。"""
    NATIONAL = "国家级"
    PROVINCIAL = "省级"
    CITY = "市级"
    COUNTY = "县级"


class MediaType(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"


class CertStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class EditRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChatMode(str, Enum):
    RAG = "rag"              # 正常：检索 + 通义千问生成
    RETRIEVAL = "retrieval"  # 降级：模型失败，返回检索片段
    KEYWORD = "keyword"      # 兜底：嵌入服务不可用，SQL LIKE 关键词检索


# ---------------------------------------------------------------------------
# M:N 关联表：项目 — 标签（复合主键；删除标签级联解除关联）
# ---------------------------------------------------------------------------
project_tag = db.Table(
    "project_tag",
    db.Column("project_id", db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


# ===========================================================================
# 1. user 平台用户
# ===========================================================================
class User(UserMixin, db.Model):
    """账号、角色、状态、联系方式。软删除：status='disabled'/'deleted' + deleted_at。"""

    __tablename__ = "user"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('sysadmin', 'admin', 'manager', 'user')", name="ck_user_role"
        ),
        db.CheckConstraint(
            "status IN ('active', 'disabled', 'deleted')", name="ck_user_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)          # 登录名（BR-10 唯一）
    password_hash = db.Column(db.String(255), nullable=False)                 # Werkzeug 哈希
    role = db.Column(db.String(20), nullable=False, default=Role.USER.value)
    real_name = db.Column(db.String(50), nullable=True)                       # 真实姓名/显示名
    phone = db.Column(db.String(20), nullable=True)                           # 绑定手机，脱敏展示
    email = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_cn, onupdate=now_cn)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # --- 密码 ---
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # --- Flask-Login 集成：禁用/注销的账号不允许建立会话 ---
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.status == UserStatus.ACTIVE.value

    # --- 角色便捷判断（权限矩阵口径） ---
    @property
    def is_sysadmin(self) -> bool:
        return self.role == Role.SYSADMIN.value

    @property
    def is_admin(self) -> bool:
        """仅 admin 角色本身；“admin 或 sysadmin”请用 can_manage_platform。"""
        return self.role == Role.ADMIN.value

    @property
    def is_manager(self) -> bool:
        return self.role == Role.MANAGER.value

    @property
    def can_manage_platform(self) -> bool:
        """管理员/系统管理员：可审核发布、归档、管理用户与分类。"""
        return self.role in (Role.ADMIN.value, Role.SYSADMIN.value)

    @property
    def display_name(self) -> str:
        return self.real_name or self.username

    def soft_delete(self, *, deactivate: bool = False) -> None:
        """注销/禁用（API-04/API-06）：一律软删除，不物理删除。"""
        self.status = UserStatus.DELETED.value if not deactivate else UserStatus.DISABLED.value
        self.deleted_at = now_cn()

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username} role={self.role} status={self.status}>"


# ===========================================================================
# 2. region 行政区划（省/市/县自关联树；防环与引用保护在服务层）
# ===========================================================================
class Region(db.Model):
    __tablename__ = "region"
    __table_args__ = (
        db.CheckConstraint(
            "level IN ('province', 'city', 'county')", name="ck_region_level"
        ),
    )

    # 下拉列表展示顺序权重（省→市→县）
    LEVEL_WEIGHT = {"province": 0, "city": 1, "county": 2}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=True)  # 省级为 NULL
    level = db.Column(db.String(20), nullable=False)
    code = db.Column(db.String(20), nullable=True)                            # 行政区划代码
    sort_order = db.Column(db.Integer, nullable=False, default=0)             # 同级排序

    # 自关联：parent(many-to-one) / children(one-to-many)
    parent = db.relationship(
        "Region",
        remote_side=[id],
        foreign_keys=[parent_id],
        backref=db.backref("children", order_by="Region.sort_order"),
    )

    @classmethod
    def ordered_for_select(cls) -> list["Region"]:
        """按树形 DFS 顺序返回全部地区（省在前、其市/县紧随其后）。

        修复 M2/M3 联调版按 level 字母序排序导致“省排最后”的问题；
        前端下拉可直接遍历本结果并按 level 缩进。
        """
        rows = cls.query.order_by(cls.sort_order.asc(), cls.id.asc()).all()
        by_id = {r.id: r for r in rows}
        children_map: dict[Optional[int], list["Region"]] = {}
        roots: list["Region"] = []
        for r in rows:
            if r.parent_id is not None and r.parent_id in by_id:
                children_map.setdefault(r.parent_id, []).append(r)
            else:
                roots.append(r)

        ordered: list["Region"] = []

        def _dfs(node: "Region") -> None:
            ordered.append(node)
            for child in children_map.get(node.id, []):
                _dfs(child)

        for root in roots:
            _dfs(root)
        return ordered

    def __repr__(self) -> str:
        return f"<Region {self.id} {self.name} level={self.level} parent_id={self.parent_id}>"


# ===========================================================================
# 3. category 非遗门类（国家级十大门类）
# ===========================================================================
class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(20), nullable=True)                            # 门类编码
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)             # 展示顺序

    def __repr__(self) -> str:
        return f"<Category {self.id} {self.name}>"


# ===========================================================================
# 4. tag 项目标签（自由标签，与项目 M:N）
# ===========================================================================
class Tag(db.Model):
    __tablename__ = "tag"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    def __repr__(self) -> str:
        return f"<Tag {self.id} {self.name}>"


# ===========================================================================
# 5. project 非遗项目（主数据、状态、可见性、浏览量、软删除）
# ===========================================================================
class Project(db.Model):
    __tablename__ = "project"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('draft', 'pending', 'published', 'rejected', 'archived')",
            name="ck_project_status",
        ),
        db.CheckConstraint("visibility IN ('public', 'internal')", name="ck_project_visibility"),
        db.CheckConstraint(
            "level IS NULL OR level IN ('国家级', '省级', '市级', '县级')",
            name="ck_project_level",
        ),
        # 「索引建议」：公开列表默认排序 / 地区 / 门类 / 浏览量 / 归档时间
        db.Index("ix_project_public_sort", "status", "visibility", "updated_at"),
        db.Index("ix_project_region", "region_id"),
        db.Index("ix_project_category", "category_id"),
        db.Index("ix_project_views", "views"),
        db.Index("ix_project_archived", "archived_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.String(300), nullable=True)                        # 列表摘要（BR-01 业务必填）
    cover_image = db.Column(db.String(255), nullable=True)                    # 封面相对路径（冗余快查）
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    level = db.Column(db.String(20), nullable=True)                           # 名录级别（可选）
    status = db.Column(db.String(20), nullable=False, default=ProjectStatus.DRAFT.value)
    visibility = db.Column(db.String(10), nullable=False, default=Visibility.PUBLIC.value)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    views = db.Column(db.Integer, nullable=False, default=0)                  # 浏览量（会话去重后 +1）
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_cn, onupdate=now_cn)
    published_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)         # 软删除标记（BR-10）
    deleted_at = db.Column(db.DateTime, nullable=True)

    # --- 关系 ---
    region = db.relationship("Region", backref="projects", lazy="joined")
    category = db.relationship("Category", backref="projects", lazy="joined")
    owner = db.relationship("User", foreign_keys=[owner_id], backref="owned_projects")
    detail = db.relationship(
        "ProjectDetail", uselist=False, back_populates="project",
        cascade="all, delete-orphan",                                          # 1:1，项目删除级联删详情
    )
    tags = db.relationship("Tag", secondary=project_tag, backref="projects", lazy="selectin")
    media_assets = db.relationship(
        "MediaAsset", backref="project", lazy="selectin",
        cascade="all, delete-orphan",                                          # 删行不删磁盘文件（文件保留）
    )

    # --- 业务便捷属性 ---
    @property
    def is_public(self) -> bool:
        """BR-07：公开 = status='published' 且 visibility='public' 且未软删除。"""
        return (
            not self.is_deleted
            and self.status == ProjectStatus.PUBLISHED.value
            and self.visibility == Visibility.PUBLIC.value
        )

    @property
    def is_archived(self) -> bool:
        return self.status == ProjectStatus.ARCHIVED.value

    def soft_delete(self) -> None:
        """BR-10 软删除：打标记 + 记录时间；status 保持不变以留审计。"""
        self.is_deleted = True
        self.deleted_at = now_cn()

    def soft_restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None

    def __repr__(self) -> str:
        return f"<Project {self.id} {self.title!r} status={self.status} visibility={self.visibility}>"


# ===========================================================================
# 6. project_detail 项目详情（1:1，长篇内容）
# ===========================================================================
class ProjectDetail(db.Model):
    __tablename__ = "project_detail"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=True)                               # 基本内容/技艺流程
    history = db.Column(db.Text, nullable=True)                               # 历史渊源
    inheritance = db.Column(db.Text, nullable=True)                           # 传承谱系
    protection = db.Column(db.Text, nullable=True)                            # 保护措施
    source_url = db.Column(db.String(500), nullable=True)                     # 公开来源链接
    updated_at = db.Column(db.DateTime, nullable=False, default=now_cn, onupdate=now_cn)

    project = db.relationship("Project", back_populates="detail")

    def __repr__(self) -> str:
        return f"<ProjectDetail {self.id} project_id={self.project_id}>"


# ===========================================================================
# 7+8. media_asset 项目媒体（封面/图集/PDF 元数据）
# ===========================================================================
class MediaAsset(db.Model):
    __tablename__ = "media_asset"
    __table_args__ = (
        db.CheckConstraint("type IN ('image', 'document')", name="ck_media_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False, default=MediaType.IMAGE.value)
    path = db.Column(db.String(255), nullable=False)                          # UUID 相对文件名
    mime = db.Column(db.String(50), nullable=True)                            # 上传时校验后的 MIME（落库审计）
    size = db.Column(db.Integer, nullable=True)                               # 字节大小（落库审计）
    is_cover = db.Column(db.Boolean, nullable=False, default=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    uploader = db.relationship("User", foreign_keys=[uploaded_by], backref="uploaded_assets")

    @property
    def is_pdf(self) -> bool:
        return self.type == MediaType.DOCUMENT.value or self.path.lower().endswith(".pdf")

    def __repr__(self) -> str:
        return f"<MediaAsset {self.id} project_id={self.project_id} type={self.type} is_cover={self.is_cover}>"


# ===========================================================================
# 9. certification 项目管理者认证（用户—项目带属性 M:N）
# ===========================================================================
class Certification(db.Model):
    """同一用户同一项目只保留一条“有效”认证（pending/approved）。

    ux_cert_active 条件唯一索引与 MySQL 不兼容 → 由服务层调用 has_active() 校验。
    """

    __tablename__ = "certification"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked')", name="ck_cert_status"
        ),
        db.Index("ix_cert_user_project", "user_id", "project_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=CertStatus.PENDING.value)
    applied_at = db.Column(db.DateTime, nullable=False, default=now_cn)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    comment = db.Column(db.String(255), nullable=True)                        # 审核意见

    user = db.relationship("User", foreign_keys=[user_id], backref="certifications")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], backref="reviewed_certifications")
    project = db.relationship("Project", backref="certifications")

    @classmethod
    def has_active(cls, user_id: int, project_id: int) -> bool:
        """是否已存在有效认证（pending/approved）——服务层防重复申请的统一入口。"""
        return (
            cls.query.filter(
                cls.user_id == user_id,
                cls.project_id == project_id,
                cls.status.in_([CertStatus.PENDING.value, CertStatus.APPROVED.value]),
            ).first()
            is not None
        )

    def __repr__(self) -> str:
        return f"<Certification {self.id} user_id={self.user_id} project_id={self.project_id} status={self.status}>"


# ===========================================================================
# 10. review_record 项目审核记录（只增不改）
# ===========================================================================
class ReviewRecord(db.Model):
    __tablename__ = "review_record"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)                         # submit/approve/reject/archive/restore...
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comment = db.Column(db.String(500), nullable=True)                        # 驳回必填（BR-05，服务层校验）
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    project = db.relationship("Project", backref="review_records")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id], backref="review_records")

    def __repr__(self) -> str:
        return f"<ReviewRecord {self.id} project_id={self.project_id} action={self.action}>"


# ===========================================================================
# 11. edit_request 归档修改申请（P1；仅归档项目可申请）
# ===========================================================================
class EditRequest(db.Model):
    """同一项目同时只允许一条 pending —— 条件唯一与 MySQL 不兼容，服务层用 pending_for() 校验。"""

    __tablename__ = "edit_request"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_edit_request_status"
        ),
        db.Index("ix_edit_request_project_status", "project_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=EditRequestStatus.PENDING.value)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    comment = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    project = db.relationship("Project", backref="edit_requests")
    requester = db.relationship("User", foreign_keys=[requester_id], backref="edit_requests")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], backref="reviewed_edit_requests")

    @classmethod
    def pending_for(cls, project_id: int) -> Optional["EditRequest"]:
        return cls.query.filter_by(
            project_id=project_id, status=EditRequestStatus.PENDING.value
        ).first()

    def __repr__(self) -> str:
        return f"<EditRequest {self.id} project_id={self.project_id} status={self.status}>"


# ===========================================================================
# 12. knowledge_chunk AI 知识块（RAG 分块文本 + float32 向量）
# ===========================================================================
class KnowledgeChunk(db.Model):
    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        # 同项目块号唯一 → 重建索引幂等（先删后插或 upsert 均可）
        db.UniqueConstraint("project_id", "chunk_no", name="ux_chunk_project_no"),
    )

    EMBEDDING_DIM = 1024  # bge-m3 输出维度（float32，约 4KB/块）

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    chunk_no = db.Column(db.Integer, nullable=False)                          # 块序号（从 1 开始）
    content = db.Column(db.Text, nullable=False)                              # 块文本（300—500 字）
    embedding = db.Column(db.LargeBinary, nullable=True)                      # float32 向量（bge-m3，1024 维）
    model = db.Column(db.String(50), nullable=True)                           # 嵌入模型标识，如 BAAI/bge-m3
    updated_at = db.Column(db.DateTime, nullable=False, default=now_cn, onupdate=now_cn)

    project = db.relationship("Project", backref="knowledge_chunks")

    # --- 向量序列化：float32 小端字节流（numpy 侧可直接 np.frombuffer(dtype='float32')） ---
    def set_embedding(self, values: Sequence[float]) -> None:
        self.embedding = array("f", values).tobytes()

    def get_embedding(self) -> Optional[list[float]]:
        if not self.embedding:
            return None
        buf = array("f")
        buf.frombytes(self.embedding)
        return buf.tolist()

    def __repr__(self) -> str:
        return f"<KnowledgeChunk {self.id} project_id={self.project_id} chunk_no={self.chunk_no}>"


# ===========================================================================
# 13. chat_log AI 问答日志（提问、答案、引用与限流计数）
# ===========================================================================
class ChatLog(db.Model):
    __tablename__ = "chat_log"
    __table_args__ = (
        db.CheckConstraint(
            "mode IS NULL OR mode IN ('rag', 'retrieval', 'keyword')", name="ck_chat_mode"
        ),
        db.Index("ix_chat_user_time", "user_id", "created_at"),                # 15 次/天限流查询
    )

    DAILY_LIMIT = 15  # BR-09：登录用户每人每天 15 次（管理员/系统管理员同样受限）

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=True)                                # 答案/检索片段
    retrieved_ids = db.Column(db.String(255), nullable=True)                  # 引用块 ID JSON，如 [3,17,42]
    mode = db.Column(db.String(20), nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    tokens = db.Column(db.Integer, nullable=True)                             # 估算 token
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    user = db.relationship("User", backref="chat_logs")

    @classmethod
    def count_today(cls, user_id: int) -> int:
        """当日提问计数（Asia/Shanghai 自然日），供 429 限流判断。"""
        return (
            db.session.query(db.func.count(cls.id))
            .filter(cls.user_id == user_id, cls.created_at >= today_start_cn())
            .scalar()
            or 0
        )

    @classmethod
    def remaining_today(cls, user_id: int) -> int:
        return max(cls.DAILY_LIMIT - cls.count_today(user_id), 0)

    def __repr__(self) -> str:
        return f"<ChatLog {self.id} user_id={self.user_id} mode={self.mode}>"


# ===========================================================================
# 14. audit_log 操作审计日志（只增不改）
# ===========================================================================
class AuditLog(db.Model):
    __tablename__ = "audit_log"
    __table_args__ = (
        db.Index("ix_audit_time", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # 匿名操作可为空
    action = db.Column(db.String(50), nullable=False)                         # login/create/update/delete/approve...
    target_type = db.Column(db.String(30), nullable=True)                     # project/user/certification...
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.String(500), nullable=True)                         # 变更摘要（脱敏后写入）
    ip = db.Column(db.String(45), nullable=True)                              # 兼容 IPv6 长度
    created_at = db.Column(db.DateTime, nullable=False, default=now_cn)

    user = db.relationship("User", backref="audit_logs")

    @classmethod
    def record(
        cls,
        action: str,
        *,
        user_id: Optional[int] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        detail: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> "AuditLog":
        """写入一条审计记录（仅 add，不 commit——由调用方服务决定事务边界）。"""
        entry = cls(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip=ip,
        )
        db.session.add(entry)
        return entry

    def __repr__(self) -> str:
        return f"<AuditLog {self.id} action={self.action} target={self.target_type}:{self.target_id}>"


__all__ = [
    "db",
    "now_cn",
    "today_start_cn",
    "project_tag",
    "Role",
    "UserStatus",
    "RegionLevel",
    "ProjectStatus",
    "Visibility",
    "ProjectLevel",
    "MediaType",
    "CertStatus",
    "EditRequestStatus",
    "ChatMode",
    "User",
    "Region",
    "Category",
    "Tag",
    "Project",
    "ProjectDetail",
    "MediaAsset",
    "Certification",
    "ReviewRecord",
    "EditRequest",
    "KnowledgeChunk",
    "ChatLog",
    "AuditLog",
]
