# [负责人：邓春鹏 | 核心交付 | 对接：方成朋(合并进全局 pytest 套件，覆盖 TC-03/08、TE-01/02/05)]
"""M2（项目管理与媒体）与 M3（分类体系与检索）自动化测试套件

对应《非遗数字化管理平台系统分析与设计报告》第 7 章：
- 功能测试：TC-03（新建项目存草稿并上传封面）、TC-08（地区/门类/标签筛选 + 浏览量降序 + 12 条/页稳定翻页）
- 异常测试：TE-01（空输入 400 逐字段提示不写库）、TE-02（sort 注入 400 白名单拒绝 + 非法文件拦截）、TE-05（不存在项目 404）
- 规则验证：BR-03（管理员创建直发 vs 管理者草稿）、BR-06（归档只读 409）、BR-07（非公开防越权 403）、
  BR-10（软删除）、图 4-3（同会话浏览量仅 +1）、API-15（分类维护权限与引用保护）。

运行方式（在本地安装 requirements.txt 后）：
    pytest -v tests/test_m2_m3_projects.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import Category, MediaAsset, Project, ProjectDetail, Region, Tag, User


def _make_png_bytes(color=(120, 40, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture()
def app(tmp_path: Path):
    test_app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SECRET_KEY": "test-secret-key",
        }
    )

    with test_app.app_context():
        db.create_all()

        # 基础账号
        users = [
            User(username="admin01", password_hash=generate_password_hash("123456"), role="admin", status="active"),
            User(username="manager01", password_hash=generate_password_hash("123456"), role="manager", status="active"),
            User(username="manager02", password_hash=generate_password_hash("123456"), role="manager", status="active"),
            User(username="user01", password_hash=generate_password_hash("123456"), role="user", status="active"),
        ]
        db.session.add_all(users)

        # 三级地区树：贵州省 -> 黔东南州 -> 雷山县 / 黎平县
        prov = Region(name="贵州省", level="province", parent_id=None)
        db.session.add(prov)
        db.session.flush()
        city = Region(name="黔东南州", level="city", parent_id=prov.id)
        db.session.add(city)
        db.session.flush()
        leishan = Region(name="雷山县", level="county", parent_id=city.id)
        liping = Region(name="黎平县", level="county", parent_id=city.id)
        db.session.add_all([leishan, liping])

        # 门类与标签
        cat_art = Category(name="传统美术")
        cat_music = Category(name="传统音乐")
        tag_miao = Tag(name="苗族")
        tag_emb = Tag(name="刺绣蜡染")
        tag_nat = Tag(name="国家级名录")
        db.session.add_all([cat_art, cat_music, tag_miao, tag_emb, tag_nat])
        db.session.commit()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login_as(client, app, username: str):
    """通过测试会话直接注入 Flask-Login 用户 ID，独立于 auth 蓝图实现。"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user is not None
        uid = str(user.id)
    with client.session_transaction() as sess:
        sess["_user_id"] = uid
        sess["_fresh"] = True


# ----------------------------------------------------------------------
# TC-03：管理者新建项目 + 上传合法封面 -> 保存为草稿且仅本人/管理员可见
# ----------------------------------------------------------------------
def test_tc03_manager_create_draft_with_cover_and_visibility(client, app):
    with app.app_context():
        leishan = Region.query.filter_by(name="雷山县").first()
        cat_art = Category.query.filter_by(name="传统美术").first()
        tag_miao = Tag.query.filter_by(name="苗族").first()
        region_id, category_id, tag_id = leishan.id, cat_art.id, tag_miao.id

    _login_as(client, app, "manager01")
    resp = client.post(
        "/projects/new?format=json",
        data={
            "title": "西江苗族刺绣草稿",
            "summary": "西江苗族刺绣代表性针法与纹样简介",
            "region_id": str(region_id),
            "category_id": str(category_id),
            "tag_ids": [str(tag_id)],
            "content": "详细工艺说明文本",
            "cover": (io.BytesIO(_make_png_bytes()), "cover.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "draft"
    assert body["cover_url"] is not None
    project_id = body["id"]
    cover_url = body["cover_url"]

    # 匿名/普通用户不可见草稿及其媒体（BR-07）
    anon_client = app.test_client()
    assert anon_client.get(f"/projects/{project_id}?format=json").status_code == 403
    assert anon_client.get(cover_url).status_code == 403

    # 本人可以查看草稿与封面图
    assert client.get(f"/projects/{project_id}?format=json").status_code == 200
    assert client.get(cover_url).status_code == 200


# ----------------------------------------------------------------------
# BR-03：管理员新建项目直接发布（published）
# ----------------------------------------------------------------------
def test_br03_admin_create_project_auto_published(client, app):
    with app.app_context():
        region_id = Region.query.filter_by(name="黎平县").first().id
        category_id = Category.query.filter_by(name="传统音乐").first().id

    _login_as(client, app, "admin01")
    resp = client.post(
        "/projects/new?format=json",
        data={
            "title": "黎平侗族大歌",
            "summary": "无伴奏多声部自然和声合唱",
            "region_id": str(region_id),
            "category_id": str(category_id),
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "published"


# ----------------------------------------------------------------------
# TC-08：三级地区级联 + 门类 + 多标签防重 + 浏览量降序 + 12 条/页稳定翻页
# ----------------------------------------------------------------------
def test_tc08_cascade_region_multitag_sort_and_stable_pagination(client, app):
    with app.app_context():
        prov = Region.query.filter_by(name="贵州省").first()
        leishan = Region.query.filter_by(name="雷山县").first()
        cat_art = Category.query.filter_by(name="传统美术").first()
        tag_miao = Tag.query.filter_by(name="苗族").first()
        tag_emb = Tag.query.filter_by(name="刺绣蜡染").first()
        admin = User.query.filter_by(username="admin01").first()

        # 造 15 条同条件公开项目（含相同浏览量以验证二级 ID 稳定排序）
        for i in range(15):
            p = Project(
                title=f"苗族刺绣示范项目-{i:02d}",
                summary="苗族刺绣示范摘要",
                region_id=leishan.id,
                category_id=cat_art.id,
                owner_id=admin.id,
                status="published",
                visibility="public",
                views=100 if i < 5 else i * 10,
            )
            p.tags = [tag_miao, tag_emb]
            db.session.add(p)
            db.session.flush()
            db.session.add(ProjectDetail(project_id=p.id, content="详细说明"))
        db.session.commit()

        prov_id, cat_id = prov.id, cat_art.id
        t1, t2 = tag_miao.id, tag_emb.id

    # 按省级地区筛选，应级联命中共 15 条挂在雷山县下的项目；多标签不产生重复行
    r1 = client.get(
        f"/projects?format=json&region_id={prov_id}&category_id={cat_id}"
        f"&tag_id={t1}&tag_id={t2}&sort=views&page=1"
    )
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["total"] == 15
    assert len(d1["items"]) == 12
    assert d1["items"][0]["views"] >= d1["items"][-1]["views"]

    r2 = client.get(
        f"/projects?format=json&region_id={prov_id}&category_id={cat_id}"
        f"&tag_id={t1}&tag_id={t2}&sort=views&page=2"
    )
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert len(d2["items"]) == 3

    # 第 1 页与第 2 页无重复、无漏条
    ids_p1 = {item["id"] for item in d1["items"]}
    ids_p2 = {item["id"] for item in d2["items"]}
    assert ids_p1.isdisjoint(ids_p2)
    assert len(ids_p1 | ids_p2) == 15


# ----------------------------------------------------------------------
# 图 4-3：同一会话浏览量仅 +1，新会话再 +1
# ----------------------------------------------------------------------
def test_session_deduplicated_views_increment(client, app):
    with app.app_context():
        reg = Region.query.filter_by(name="雷山县").first()
        cat = Category.query.filter_by(name="传统美术").first()
        admin = User.query.filter_by(username="admin01").first()
        p = Project(
            title="浏览量测试项目",
            summary="摘要",
            region_id=reg.id,
            category_id=cat.id,
            owner_id=admin.id,
            status="published",
            visibility="public",
            views=10,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    # 同一客户端连续刷新两次，views 只从 10 -> 11
    assert client.get(f"/projects/{pid}?format=json").get_json()["views"] == 11
    assert client.get(f"/projects/{pid}?format=json").get_json()["views"] == 11

    # 新会话访问，views 增至 12
    client2 = app.test_client()
    assert client2.get(f"/projects/{pid}?format=json").get_json()["views"] == 12


# ----------------------------------------------------------------------
# TE-01：空输入返回 400 + 逐字段错误字典，且不写库
# ----------------------------------------------------------------------
def test_te01_empty_project_submission_returns_400_field_errors(client, app):
    _login_as(client, app, "manager01")
    resp = client.post("/projects/new?format=json", data={})
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert {"title", "summary", "region_id", "category_id"}.issubset(errors.keys())
    with app.app_context():
        assert Project.query.count() == 0


# ----------------------------------------------------------------------
# TE-02：非法排序字段白名单拦截 + 伪造图片/PDF 文件头拦截
# ----------------------------------------------------------------------
def test_te02_invalid_sort_and_spoofed_media_rejected(client, app):
    # 1. SQL 注入排序参数必须返回 400
    resp_sort = client.get("/projects?format=json&sort=drop table;")
    assert resp_sort.status_code == 400

    # 2. 伪造 .png 后缀的文本文件必须拦截返回 400
    with app.app_context():
        region_id = Region.query.filter_by(name="雷山县").first().id
        category_id = Category.query.filter_by(name="传统美术").first().id

    _login_as(client, app, "manager01")
    resp_fake_img = client.post(
        "/projects/new?format=json",
        data={
            "title": "伪造图片测试",
            "summary": "摘要",
            "region_id": str(region_id),
            "category_id": str(category_id),
            "cover": (io.BytesIO(b"not-a-real-png-binary"), "evil.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert resp_fake_img.status_code == 400

    # 3. 合法 PDF 附件放行，伪造 PDF 拦截
    resp_fake_pdf = client.post(
        "/projects/new?format=json",
        data={
            "title": "伪造PDF测试",
            "summary": "摘要",
            "region_id": str(region_id),
            "category_id": str(category_id),
            "attachments": (io.BytesIO(b"<html>fake</html>"), "fake.pdf", "application/pdf"),
        },
        content_type="multipart/form-data",
    )
    assert resp_fake_pdf.status_code == 400

    resp_valid_pdf = client.post(
        "/projects/new?format=json",
        data={
            "title": "合法PDF测试",
            "summary": "摘要",
            "region_id": str(region_id),
            "category_id": str(category_id),
            "attachments": (io.BytesIO(_make_pdf_bytes()), "doc.pdf", "application/pdf"),
        },
        content_type="multipart/form-data",
    )
    assert resp_valid_pdf.status_code == 201


# ----------------------------------------------------------------------
# TE-05 & BR-06：不存在项目 404；归档项目只读编辑返回 409
# ----------------------------------------------------------------------
def test_te05_not_found_and_br06_archived_readonly(client, app):
    assert client.get("/projects/999999?format=json").status_code == 404

    with app.app_context():
        reg = Region.query.filter_by(name="雷山县").first()
        cat = Category.query.filter_by(name="传统美术").first()
        mgr = User.query.filter_by(username="manager01").first()
        p = Project(
            title="已归档项目",
            summary="归档摘要",
            region_id=reg.id,
            category_id=cat.id,
            owner_id=mgr.id,
            status="archived",
            visibility="public",
            views=5,
        )
        db.session.add(p)
        db.session.commit()
        pid, rid, cid = p.id, reg.id, cat.id

    _login_as(client, app, "manager01")
    resp = client.post(
        f"/projects/{pid}/edit?format=json",
        data={
            "title": "尝试修改已归档项目",
            "summary": "新摘要",
            "region_id": str(rid),
            "category_id": str(cid),
        },
    )
    assert resp.status_code == 409


# ----------------------------------------------------------------------
# API-15：分类体系维护权限拦截与被引用节点删除保护
# ----------------------------------------------------------------------
def test_api15_taxonomy_permission_and_reference_protection(client, app):
    # 普通用户访问 /admin/taxonomy 返回 403
    _login_as(client, app, "user01")
    assert client.get("/admin/taxonomy?format=json").status_code == 403

    # 管理员删除含下级地区的贵州省 -> 返回 409
    _login_as(client, app, "admin01")
    with app.app_context():
        prov_id = Region.query.filter_by(name="贵州省").first().id
    resp_del_parent = client.post(
        "/admin/taxonomy?format=json",
        data={"entity": "region", "action": "delete", "id": str(prov_id)},
    )
    assert resp_del_parent.status_code == 409