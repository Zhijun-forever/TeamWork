# [负责人：邓春鹏 | 核心交付 | 对接：方成朋（并入主仓 pytest 回归）]
"""M2/M3 接口自动化测试（对齐《系统接口清单》V2.0）

覆盖 API-14 ~ API-21 与 API-33：
- 列表：参数（scope/q/region/category/tag/level/status/sort/order/page/per_page）、
  分页结构、排序白名单、nulls last、越权 403 / 未登录 401；
- 详情：project/detail/tags/media/review_records/permissions 结构、同会话浏览量去重；
- 新建/编辑：multipart 字段、manager→draft / admin→published、400 data.errors、
  413 文件超限、归档只读与待审锁定 409；
- 状态机：submit/approve/reject/archive/restore/request_edit/delete，禁止自审（BR-04）；
- 分类：公开字典、admin 字典、维护 CRUD 与被引用/防环 409；
- 媒体：/media/<path> 读取、公开可见性、404 防探测；
- 统一信封与时间格式（``YYYY-MM-DD HH:MM:SS``）。

运行：``python -m pytest -q tests/test_m2_m3_projects.py``（CSRF 在测试中关闭）
"""

from __future__ import annotations

import io
import re

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    Category,
    Certification,
    EditRequest,
    MediaAsset,
    Project,
    ProjectDetail,
    Region,
    ReviewRecord,
    Tag,
    User,
)

TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


# ---------------------------------------------------------------------------
# 夹具与工具
# ---------------------------------------------------------------------------
def make_png(color=(120, 40, 40), size=(80, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SECRET_KEY": "test-secret",
        }
    )
    with application.app_context():
        db.create_all()
        db.session.add_all(
            [
                User(username="sysadmin", password_hash=generate_password_hash("123456"), role="sysadmin"),
                User(username="admin01", password_hash=generate_password_hash("123456"), role="admin"),
                User(username="manager01", password_hash=generate_password_hash("123456"), role="manager"),
                User(username="manager02", password_hash=generate_password_hash("123456"), role="manager"),
                User(username="user01", password_hash=generate_password_hash("123456"), role="user"),
            ]
        )
        province = Region(name="贵州省", level="province", sort_order=0)
        db.session.add(province)
        db.session.flush()
        city = Region(name="黔东南州", level="city", parent_id=province.id, sort_order=0)
        db.session.add(city)
        db.session.flush()
        db.session.add_all(
            [
                Region(name="雷山县", level="county", parent_id=city.id, sort_order=0),
                Region(name="黎平县", level="county", parent_id=city.id, sort_order=1),
            ]
        )
        db.session.add_all(
            [
                Category(name="传统美术", sort_order=6),
                Category(name="传统音乐", sort_order=1),
                Tag(name="苗族"),
                Tag(name="刺绣蜡染"),
            ]
        )
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def ids(app):
    with app.app_context():
        return {
            "province": Region.query.filter_by(name="贵州省").first().id,
            "city": Region.query.filter_by(name="黔东南州").first().id,
            "leishan": Region.query.filter_by(name="雷山县").first().id,
            "liping": Region.query.filter_by(name="黎平县").first().id,
            "art": Category.query.filter_by(name="传统美术").first().id,
            "music": Category.query.filter_by(name="传统音乐").first().id,
            "admin": User.query.filter_by(username="admin01").first().id,
            "manager": User.query.filter_by(username="manager01").first().id,
            "manager2": User.query.filter_by(username="manager02").first().id,
            "user": User.query.filter_by(username="user01").first().id,
        }


def login_as(client, app, username: str) -> None:
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user is not None
        uid = str(user.id)
    with client.session_transaction() as sess:
        sess["_user_id"] = uid
        sess["_fresh"] = True


def make_project(
    app,
    *,
    title: str,
    region_id: int,
    category_id: int,
    owner_id: int,
    status: str = "published",
    visibility: str = "public",
    views: int = 0,
    level: str | None = "国家级",
    tags: list[str] | None = None,
) -> int:
    with app.app_context():
        project = Project(
            title=title,
            summary=f"{title}摘要",
            region_id=region_id,
            category_id=category_id,
            owner_id=owner_id,
            status=status,
            visibility=visibility,
            views=views,
            level=level,
        )
        if tags:
            project.tags = Tag.query.filter(Tag.name.in_(tags)).all()
        db.session.add(project)
        db.session.flush()
        db.session.add(ProjectDetail(project_id=project.id, content=f"{title}正文"))
        db.session.commit()
        return project.id


# ---------------------------------------------------------------------------
# API-14 查询项目列表
# ---------------------------------------------------------------------------
def test_api14_envelope_pagination_and_item_fields(client, app, ids):
    for index in range(3):
        make_project(
            app, title=f"苗族刺绣-{index}", region_id=ids["leishan"],
            category_id=ids["art"], owner_id=ids["admin"], tags=["苗族"],
        )

    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.get_json()
    assert body["code"] == "OK"
    assert body["message"] == "success"
    data = body["data"]
    assert set(data) == {"items", "total", "page", "per_page"}
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["per_page"] == 12

    item = data["items"][0]
    assert set(item) >= {
        "id", "title", "summary", "cover", "region", "province", "category",
        "region_id", "category_id", "level", "status", "visibility", "owner",
        "views", "tags", "created_at", "updated_at",
    }
    # 地区全路径与省份
    assert item["region"] == "贵州省黔东南州雷山县"
    assert item["province"] == "贵州省"
    assert item["owner"]["username"] == "admin01"
    assert item["tags"] == ["苗族"]
    # 时间格式：空格分隔，非 ISO T
    assert TIME_PATTERN.match(item["created_at"])
    assert "T" not in item["created_at"]


def test_api14_filters_accept_name_or_id(client, app, ids):
    make_project(
        app, title="雷山苗族刺绣", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["admin"], tags=["苗族", "刺绣蜡染"],
    )
    make_project(
        app, title="黎平侗族大歌", region_id=ids["liping"], category_id=ids["music"],
        owner_id=ids["admin"], level="省级", tags=["苗族"],
    )

    def total(query: str) -> int:
        response = client.get(f"/api/projects?{query}")
        assert response.status_code == 200, response.get_json()
        return response.get_json()["data"]["total"]

    assert total(f"region={ids['province']}") == 2          # 省 → 级联
    assert total("region=贵州省") == 2                       # 名称
    assert total(f"region={ids['leishan']}") == 1
    assert total(f"category={ids['art']}") == 1
    assert total("category=传统音乐") == 1
    assert total("tag=苗族") == 2                            # 名称
    assert total("tag=苗族,刺绣蜡染") == 1                    # 多标签交集
    assert total("level=国家级") == 1
    assert total("level=省级") == 1
    assert total("q=侗族") == 1
    assert total("q=不存在的词") == 0


def test_api14_sort_whitelist_order_and_nulls_last(client, app, ids):
    make_project(
        app, title="甲", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["admin"], views=5,
    )
    make_project(
        app, title="乙", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["admin"], views=50,
    )

    descending = client.get("/api/projects?sort=views&order=desc").get_json()["data"]
    assert [item["views"] for item in descending["items"]] == [50, 5]
    ascending = client.get("/api/projects?sort=views&order=asc").get_json()["data"]
    assert [item["views"] for item in ascending["items"]] == [5, 50]

    # published_at 也是白名单之一（V2.0 新增）
    assert client.get("/api/projects?sort=published_at").status_code == 200

    for query in ("sort=drop table", "sort=title", "order=sideways", "level=世界级", "page=abc"):
        response = client.get(f"/api/projects?{query}")
        assert response.status_code == 400, query
        assert response.get_json()["data"] is None


def test_api14_scope_rules(client, app, ids):
    make_project(
        app, title="管理员草稿", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["admin"], status="draft",
    )

    # 未登录访问 mine/all → 401（不是 403，也不是 302）
    assert client.get("/api/projects?scope=mine").status_code == 401
    assert client.get("/api/projects?scope=all").status_code == 401

    login_as(client, app, "user01")
    assert client.get("/api/projects?scope=all").status_code == 403
    assert client.get("/api/projects?scope=mine").get_json()["data"]["total"] == 0

    login_as(client, app, "admin01")
    assert client.get("/api/projects?scope=all").get_json()["data"]["total"] == 1
    # 公开列表不含草稿
    assert client.get("/api/projects").get_json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# API-15 查看项目详情
# ---------------------------------------------------------------------------
def test_api15_detail_payload_and_view_dedupe(client, app, ids):
    project_id = make_project(
        app, title="安顺地戏", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], views=10, tags=["苗族"],
    )

    first = client.get(f"/api/projects/{project_id}")
    assert first.status_code == 200
    data = first.get_json()["data"]
    assert set(data) == {"project", "detail", "tags", "media", "review_records", "permissions"}
    assert data["project"]["views"] == 11              # 同会话 +1
    assert "published_at" in data["project"]
    assert "archived_at" in data["project"]
    assert data["detail"]["content"].endswith("正文")
    assert data["tags"] == ["苗族"]
    assert data["permissions"]["can_edit"] is False     # 匿名

    second = client.get(f"/api/projects/{project_id}")
    assert second.get_json()["data"]["project"]["views"] == 11   # 同会话不重复 +1

    other_client = app.test_client()
    assert other_client.get(f"/api/projects/{project_id}").get_json()["data"]["project"]["views"] == 12


def test_api15_not_found_and_non_public(client, app, ids):
    assert client.get("/api/projects/999999").status_code == 404

    draft_id = make_project(
        app, title="内部草稿", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="draft",
    )
    assert client.get(f"/api/projects/{draft_id}").status_code == 403

    login_as(client, app, "manager01")
    assert client.get(f"/api/projects/{draft_id}").status_code == 200


# ---------------------------------------------------------------------------
# API-16 新建项目
# ---------------------------------------------------------------------------
def test_api16_manager_creates_draft_with_cover(client, app, ids):
    login_as(client, app, "manager01")
    response = client.post(
        "/api/projects/new",
        data={
            "title": "西江苗族刺绣",
            "summary": "平绣、辫绣、锁绣",
            "region_id": str(ids["leishan"]),
            "category_id": str(ids["art"]),
            "level": "国家级",
            "tags": ["苗族", "刺绣蜡染"],
            "content": "详细工艺说明",
            "history": "历史渊源",
            "inheritance": "传承谱系",
            "protection": "保护措施",
            "source_url": "https://www.ihchina.cn/",
            "cover": (io.BytesIO(make_png()), "cover.png", "image/png"),
            "attachments": (io.BytesIO(make_pdf()), "doc.pdf", "application/pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200          # V2.0：创建也返回 200
    data = response.get_json()["data"]
    project = data["project"]
    assert project["status"] == "draft"          # manager → draft
    assert project["cover"].startswith("/media/project/")
    assert sorted(project["tags"]) == ["刺绣蜡染", "苗族"]

    # 封面可读，媒体路径带 project/ 前缀（API-33）
    media = client.get(f"/api/projects/{project['id']}").get_json()["data"]["media"]
    assert len(media) == 2
    cover = next(item for item in media if item["is_cover"])
    assert client.get(cover["url"]).status_code == 200


def test_api16_admin_publish_default_and_flag(client, app, ids):
    login_as(client, app, "admin01")
    base = {
        "title": "黎平侗族大歌",
        "summary": "多声部自然和声",
        "region_id": str(ids["liping"]),
        "category_id": str(ids["music"]),
    }
    published = client.post("/api/projects/new", data=base)
    assert published.get_json()["data"]["project"]["status"] == "published"

    draft = client.post("/api/projects/new", data={**base, "title": "管理员草稿", "publish": "0"})
    assert draft.get_json()["data"]["project"]["status"] == "draft"


def test_api16_validation_errors_and_media_limits(client, app, ids):
    login_as(client, app, "manager01")

    empty = client.post("/api/projects/new", data={})
    assert empty.status_code == 400
    body = empty.get_json()
    assert body["code"] == "BAD_REQUEST"
    assert {"title", "summary", "region_id", "category_id"} <= set(body["data"]["errors"])

    base = {
        "title": "媒体测试",
        "summary": "摘要",
        "region_id": str(ids["leishan"]),
        "category_id": str(ids["art"]),
    }
    fake_image = client.post(
        "/api/projects/new",
        data={**base, "cover": (io.BytesIO(b"not-a-png"), "evil.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert fake_image.status_code == 400
    assert "media" in fake_image.get_json()["data"]["errors"]

    too_big = client.post(
        "/api/projects/new",
        data={**base, "cover": (io.BytesIO(b"0" * (10 * 1024 * 1024 + 1)), "big.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert too_big.status_code == 413
    assert too_big.get_json()["code"] == "FILE_TOO_LARGE"

    fake_pdf = client.post(
        "/api/projects/new",
        data={**base, "attachments": (io.BytesIO(b"<html>"), "fake.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )
    assert fake_pdf.status_code == 400


def test_api16_requires_project_role(client, app, ids):
    assert client.post("/api/projects/new", data={}).status_code == 401
    login_as(client, app, "user01")
    assert client.post("/api/projects/new", data={}).status_code == 403


# ---------------------------------------------------------------------------
# API-17 编辑项目
# ---------------------------------------------------------------------------
def test_api17_edit_and_state_conflicts(client, app, ids):
    login_as(client, app, "manager01")
    project_id = make_project(
        app, title="待编辑", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="draft",
    )

    response = client.post(
        f"/api/projects/{project_id}/edit",
        data={
            "title": "改后的标题",
            "summary": "改后的摘要",
            "region_id": str(ids["liping"]),
            "category_id": str(ids["music"]),
            "level": "省级",
            "tags": ["苗族"],
        },
    )
    assert response.status_code == 200
    project = response.get_json()["data"]["project"]
    assert project["title"] == "改后的标题"
    assert project["level"] == "省级"
    assert project["tags"] == ["苗族"]

    # 归档只读 → 409
    with app.app_context():
        row = db.session.get(Project, project_id)
        row.status = "archived"
        db.session.commit()
    assert client.post(
        f"/api/projects/{project_id}/edit",
        data={"title": "x", "summary": "y", "region_id": str(ids["leishan"]), "category_id": str(ids["art"])},
    ).status_code == 409

    # 待审锁定（管理者）→ 409
    pending_id = make_project(
        app, title="待审", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="pending",
    )
    assert client.post(
        f"/api/projects/{pending_id}/edit",
        data={"title": "x", "summary": "y", "region_id": str(ids["leishan"]), "category_id": str(ids["art"])},
    ).status_code == 409

    # 非作者管理者 → 403
    other_id = make_project(
        app, title="他人项目", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager2"], status="draft",
    )
    assert client.post(
        f"/api/projects/{other_id}/edit",
        data={"title": "x", "summary": "y", "region_id": str(ids["leishan"]), "category_id": str(ids["art"])},
    ).status_code == 403


# ---------------------------------------------------------------------------
# API-18 状态机
# ---------------------------------------------------------------------------
def test_api18_submit_approve_archive_restore(client, app, ids):
    login_as(client, app, "manager01")
    project_id = make_project(
        app, title="状态机", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="draft",
    )

    submitted = client.post(f"/api/projects/{project_id}/status", json={"action": "submit"})
    assert submitted.status_code == 200
    assert submitted.get_json()["data"]["project"]["status"] == "pending"

    # 管理者不能审核
    assert client.post(
        f"/api/projects/{project_id}/status", json={"action": "approve"}
    ).status_code == 403

    login_as(client, app, "admin01")
    approved = client.post(f"/api/projects/{project_id}/status", json={"action": "approve"})
    assert approved.get_json()["data"]["project"]["status"] == "published"
    # API-18 返回 ProjectItem；published_at/archived_at 属于详情的 project 全字段
    detail = client.get(f"/api/projects/{project_id}").get_json()["data"]["project"]
    assert detail["published_at"] is not None
    assert detail["archived_at"] is None

    archived = client.post(f"/api/projects/{project_id}/status", json={"action": "archive"})
    assert archived.get_json()["data"]["project"]["status"] == "archived"
    assert client.get(f"/api/projects/{project_id}").get_json()["data"]["project"]["archived_at"] is not None

    restored = client.post(f"/api/projects/{project_id}/status", json={"action": "restore"})
    assert restored.get_json()["data"]["project"]["status"] == "published"
    assert client.get(f"/api/projects/{project_id}").get_json()["data"]["project"]["archived_at"] is None

    # 审核记录已写入
    with app.app_context():
        actions = [
            record.action
            for record in ReviewRecord.query.filter_by(project_id=project_id)
            .order_by(ReviewRecord.id)
            .all()
        ]
    assert actions == ["submit", "approve", "archive", "restore"]


def test_api18_reject_requires_comment_and_status_guard(client, app, ids):
    login_as(client, app, "admin01")
    pending_id = make_project(
        app, title="待驳回", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="pending",
    )

    missing = client.post(f"/api/projects/{pending_id}/status", json={"action": "reject"})
    assert missing.status_code == 400
    assert "comment" in missing.get_json()["data"]["errors"]

    rejected = client.post(
        f"/api/projects/{pending_id}/status",
        json={"action": "reject", "comment": "材料不全"},
    )
    assert rejected.get_json()["data"]["project"]["status"] == "rejected"

    # 非 pending 再审核 → 409
    conflict = client.post(f"/api/projects/{pending_id}/status", json={"action": "approve"})
    assert conflict.status_code == 409
    assert conflict.get_json()["code"] == "CONFLICT"

    # 非法 action → 400
    bad = client.post(f"/api/projects/{pending_id}/status", json={"action": "fly"})
    assert bad.status_code == 400
    assert "action" in bad.get_json()["data"]["errors"]


def test_api18_forbid_self_review(client, app, ids):
    pending_id = make_project(
        app, title="管理员自己的待审项目", region_id=ids["leishan"],
        category_id=ids["art"], owner_id=ids["admin"], status="pending",
    )
    login_as(client, app, "admin01")
    response = client.post(f"/api/projects/{pending_id}/status", json={"action": "approve"})
    assert response.status_code == 403


def test_api18_delete_rules(client, app, ids):
    login_as(client, app, "manager01")
    draft_id = make_project(
        app, title="可删草稿", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="draft",
    )
    assert client.post(
        f"/api/projects/{draft_id}/status", json={"action": "delete"}
    ).status_code == 200
    with app.app_context():
        assert db.session.get(Project, draft_id).is_deleted is True

    published_id = make_project(
        app, title="已发布", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="published",
    )
    assert client.post(
        f"/api/projects/{published_id}/status", json={"action": "delete"}
    ).status_code == 403

    login_as(client, app, "admin01")
    assert client.post(
        f"/api/projects/{published_id}/status", json={"action": "delete"}
    ).status_code == 200


def test_api18_request_edit_for_archived(client, app, ids):
    login_as(client, app, "manager01")
    project_id = make_project(
        app, title="归档项目", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["manager"], status="archived",
    )
    with app.app_context():
        db.session.add(
            Certification(
                user_id=ids["manager"], project_id=project_id, status="approved"
            )
        )
        db.session.commit()

    response = client.post(
        f"/api/projects/{project_id}/status",
        json={"action": "request_edit", "comment": "补充保护单位"},
    )
    assert response.status_code == 200
    with app.app_context():
        assert EditRequest.pending_for(project_id) is not None

    # 重复申请 → 409
    again = client.post(
        f"/api/projects/{project_id}/status",
        json={"action": "request_edit", "comment": "再来一次"},
    )
    assert again.status_code == 409


# ---------------------------------------------------------------------------
# API-19 / API-20 / API-21 分类
# ---------------------------------------------------------------------------
def test_api19_and_api20_taxonomy_dicts(client, app):
    public = client.get("/api/taxonomy")
    assert public.status_code == 200                 # 公开字典，无需登录
    data = public.get_json()["data"]
    assert set(data) == {"regions", "categories", "tags"}
    # regions 为树形 DFS 序：省在第一个
    assert data["regions"][0]["level"] == "province"
    assert data["regions"][0]["parent_id"] is None

    assert client.get("/api/admin/taxonomy").status_code == 401
    login_as(client, app, "manager01")
    assert client.get("/api/admin/taxonomy").status_code == 403
    login_as(client, app, "admin01")
    assert client.get("/api/admin/taxonomy").status_code == 200


def test_api21_taxonomy_crud_and_protections(client, app, ids):
    login_as(client, app, "admin01")

    created = client.post("/api/admin/taxonomy", json={"type": "tag", "action": "create", "name": "新增标签"})
    assert created.status_code == 200
    assert created.get_json()["data"]["message"] == "已创建"

    duplicated = client.post("/api/admin/taxonomy", json={"type": "tag", "action": "create", "name": "新增标签"})
    assert duplicated.status_code == 409

    bad_level = client.post(
        "/api/admin/taxonomy",
        json={"type": "region", "action": "create", "name": "某地", "level": "planet"},
    )
    assert bad_level.status_code == 400
    assert "level" in bad_level.get_json()["data"]["errors"]

    # 有下级地区 → 409
    assert client.post(
        "/api/admin/taxonomy",
        json={"type": "region", "action": "delete", "id": ids["province"]},
    ).status_code == 409

    # 被项目引用 → 409
    make_project(
        app, title="占用门类", region_id=ids["leishan"], category_id=ids["art"],
        owner_id=ids["admin"],
    )
    assert client.post(
        "/api/admin/taxonomy",
        json={"type": "category", "action": "delete", "id": ids["art"]},
    ).status_code == 409

    # 地区防环：把省挂到自己的县级下 → 409
    assert client.post(
        "/api/admin/taxonomy",
        json={
            "type": "region",
            "action": "update",
            "id": ids["province"],
            "parent_id": ids["leishan"],
        },
    ).status_code == 409

    # 标签删除会解除 M:N 关联
    deleted = client.post(
        "/api/admin/taxonomy", json={"type": "tag", "action": "delete", "id": 1}
    )
    assert deleted.status_code == 200


# ---------------------------------------------------------------------------
# API-33 媒体
# ---------------------------------------------------------------------------
def test_api33_media_visibility_and_404(client, app, ids):
    login_as(client, app, "manager01")
    created = client.post(
        "/api/projects/new",
        data={
            "title": "媒体项目",
            "summary": "摘要",
            "region_id": str(ids["leishan"]),
            "category_id": str(ids["art"]),
            "cover": (io.BytesIO(make_png()), "cover.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    project_id = created.get_json()["data"]["project"]["id"]
    cover_url = created.get_json()["data"]["project"]["cover"]

    # 草稿的媒体：匿名 404（防探测），作者 200
    anonymous = app.test_client()
    assert anonymous.get(cover_url).status_code == 404
    assert client.get(cover_url).status_code == 200

    # 发布后公开可读
    client.post(f"/api/projects/{project_id}/status", json={"action": "submit"})
    login_as(client, app, "admin01")
    client.post(f"/api/projects/{project_id}/status", json={"action": "approve"})
    assert anonymous.get(cover_url).status_code == 200

    # 不存在的文件 → 404
    assert anonymous.get("/media/project/not-exists.jpg").status_code == 404

    # 媒体记录里的 URL 与封面一致
    detail = anonymous.get(f"/api/projects/{project_id}").get_json()["data"]
    assert detail["media"][0]["url"] == cover_url