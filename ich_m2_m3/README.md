> **V2.0 更新（2026-11-28，邓春鹏）**：主仓已切换为 Vue3 SPA + `/api` JSON 接口
> （以仓库根目录《系统接口清单》V2.0 为准）。本目录的 `app/projects.py`、
> `app/services/project_service.py`、`app/services/query_builder.py`、
> `tests/test_m2_m3_projects.py` 已按 V2.0 重写（实现 API-14~21、API-33）。
> 下文 V1.1 时期的“Jinja 页面 + 302 表单重定向 / tag_ids / region_id 参数 / `/media/<asset_id>`”
> 等描述**已作废**，仅保留各文件用途说明供查阅。
# 非遗数字化管理平台 — M2 & M3 模块代码说明（邓春鹏）

本目录包含 **M2（项目管理与媒体安全）** 与 **M3（分类体系、多条件检索与 50 条非遗演示数据）** 的完整实现、联调模板及自动化测试用例，已按《非遗数字化管理平台系统分析与设计报告》第 5–7 章规范拆分为独立可运行结构。

---

## 一、全目录逐文件说明（方便队友快速查阅）

| 文件路径 | 分类 | 功能说明 | 主要对接队友 & 合入方式 |
| --- | --- | --- | --- |
| `app/services/query_builder.py` | **核心交付** | 封装 `ProjectQueryBuilder`：公开/范围过滤（BR-02/07）、省市县三级地区级联查询、M:N 标签防重（`EXISTS`）、4 种排序白名单（拦截 TE-02 注入）及二级 ID 稳定分页（12 条/页，保 TC-08）。 | **周世航 / 方成朋**：直接合入主仓 `app/services/`。 |
| `app/services/project_service.py` | **核心交付** | 封装 `ProjectService` 与 `TaxonomyService`：项目 CRUD、BR-01 逐字段校验、BR-03 管理员直发/管理者草稿分流、BR-06 归档只读锁定、BR-10 软删除、同会话浏览量去重（图 4-3）、媒体四重安全校验（后缀/MIME/大小/Pillow 图片与 `%PDF-` 文件头）及地区防环/引用保护删除。 | **周世航 / 方成朋**：直接合入主仓 `app/services/`；状态流转（提交审核/通过/驳回/归档/恢复）已留给 `ReviewService`。 |
| `app/projects.py` | **核心交付** | M2/M3 蓝图路由层（`projects_bp`）：覆盖 API-10~13、API-15 分类维护、软删除及 `/media/<asset_id>` 受控媒体读取；支持 Jinja2 页面与 `?format=json` 双返回模式。 | **周世航 / 谭应锋**：合入主仓 `app/` 并在应用工厂注册 `projects_bp`。 |
| `seed.py` | **核心交付** | 幂等数据初始化脚本：写入 4 个演示账号（`sysadmin/admin01/manager01/user01`，密码 `123456`）、十大门类、26 节点贵州省市县三级地区树、20 个标签与 **50 个公开非遗项目**（已覆盖表 7-3 AI 评测题 Q1–Q6：苗族刺绣、侗族大歌、贵州传统音乐、传统戏剧与保护单位）。 | **周世航**：直接合入主仓根目录，供演示与 RAG 索引构建使用。 |
| `tests/test_m2_m3_projects.py` | **核心交付** | 基于内存 SQLite 的 `pytest` 自动化测试套件，覆盖 TC-03、TC-08、TE-01、TE-02、TE-05 及 BR-03/06/07/10、会话浏览量去重、伪造文件拦截和 API-15 分类保护。 | **方成朋**：直接合入主仓 `tests/` 统一回归。 |
| `app/templates/base.html` | 联调模板 | Bootstrap 5 极简公共布局（导航栏与 Flash 提示）。 | **谭应锋**：合入时可替换为小组统一母版及本地静态资源。 |
| `app/templates/projects/list.html` | 联调模板 | 项目库列表页（筛选栏、多标签勾选、4 种排序、12 条/页分页）。 | **谭应锋**：美化时请保留表单控件 `name` 属性与分页查询参数。 |
| `app/templates/projects/detail.html` | 联调模板 | 项目详情页（封面/图集/PDF 预览、正文三段与编辑/删除按钮）。 | **谭应锋 / 方成朋**：美化并按需挂接审核/归档操作按钮。 |
| `app/templates/projects/form.html` | 联调模板 | 新建/编辑共用表单页（带逐字段 `errors` 高亮回显与可选 `csrf_token` 兼容）。 | **谭应锋**：保留 `enctype="multipart/form-data"` 与字段回显。 |
| `app/templates/admin/taxonomy.html` | 联调模板 | 管理员分类维护页（地区树、十大门类、自由标签的新增与安全删除）。 | **谭应锋 / 周世航**：美化并挂入管理员后台菜单。 |
| `app/__init__.py` | 自测底座 | 最小应用工厂（配置 SQLite、`UPLOAD_FOLDER` 与 12MB 上传上限）。 | **仅本地独立运行用**：合入主仓时以周世航版本为准。 |
| `app/models.py` | 自测底座 | 按报告图 5-2 / 表 5-2/5-3 编写的 8 张核心表 ORM 模型。 | **仅本地独立运行用**：合入主仓时以周世航版本为准，核对 `Project.summary` 与软删除字段即可。 |
| `app/permissions.py` | 自测底座 | 按报告代码 6-2 编写的 `role_required` 与 `can_edit_project`。 | **仅本地独立运行用**：合入主仓时以周世航版本为准。 |
| `run.py` | 自测底座 | 本地一键启动脚本（监听 `127.0.0.1:5000`）。 | **仅本地独立运行用**。 |
| `requirements.txt` | 环境配置 | 运行本模块所需 Python 依赖清单（Python 3.12 + Flask 3.x）。 | **周世航**：按需合并到主仓依赖清单。 |
| `.gitignore` | Git 配置 | 忽略本地 SQLite 数据库、缓存与测试上传文件，保持仓库干净。 | 随目录提交即可。 |

---

## 二、队友快速对接指南

- **周世航（组长 / 架构 & AI）**：
  1. 在主仓 `models.py` 中确认 `Project` 表保留 `summary` 列，并确认软删除采用 `status == "deleted"`（若改用 `deleted_at`，同步修改 `query_builder.py` 与 `project_service.py` 中的过滤条件即可）。
  2. 在主仓 `app/__init__.py` 注册 `from app.projects import projects_bp; app.register_blueprint(projects_bp)`。
  3. 运行 `python seed.py` 即可得到 50 条 `published + public` 非遗长文本，直接用于 `bge-m3` 切块与 Q1–Q6 问答评测。
- **谭应锋（前端）**：
  1. `GET /projects` 支持参数：`region_id`、`category_id`、`tag_id`（可重复传参或逗号分隔）、`tag_mode`（`all`/`any`）、`q`、`status`、`sort`（`updated_at`/`views`/`created_at`/`archived_at`）、`page`、`scope`（`public`/`mine`/`all`）。
  2. 所有接口加上 `?format=json` 可直接查看 JSON 数据结构，便于前端核对字段。
- **方成朋（审核归档 & 测试）**：
  1. `ProjectService` 不越界处理审核状态流转，并在编辑入口已拦截 `archived`（409）与管理者编辑 `pending`（409），避免与 `ReviewService` 冲突。
  2. 运行 `pytest -v tests/test_m2_m3_projects.py` 可直接复现 M2/M3 全部功能与异常用例。

---

## 三、本地 3 步快速验证

```bash
pip install -r requirements.txt
python seed.py
pytest -v tests/test_m2_m3_projects.py
python run.py
# 浏览器打开 http://127.0.0.1:5000/projects
```
