# 非遗数字化管理平台 · Element 风格前端工程 v1.1

全部页面按 Element 组件默认规范构建：默认蓝、白卡片、浅灰背景、4px 控件圆角、清晰表格，无古风装饰。当前版本已完成演示字样清理、帮助中心与通知中心、整体尺寸上调，并接入与《系统接口清单 V1.1》对齐的接口层。

## 怎么看

双击打开 **`index.html`**（页面地图），或直接打开任意页面。

- 23 个 HTML 页面，无构建、无 CDN、无前端框架，离线可打开。
- 数据与接口调用统一走 `assets/js/api.js`；后端未完成时默认 mock 模式，切换方式见下文。
- 桌面建议 1440 宽查看，移动端 390 宽已适配。
- 更完整的讲解流程、接口映射和角色说明见 **[演示文档.md](演示文档.md)**。

## 页面清单

### 公众端（7 页）

| 页面 | 文件 | 覆盖内容 |
|---|---|---|
| 首页 | `site/home.html` | 首屏、数据概览、十大门类、近期项目、地区、AI 入口、平台能力 |
| 项目库 | `site/projects.html` | 关键词 / 地区 / 门类 / 标签 / 排序筛选、筛选标签、卡片列表、分页 |
| 项目详情 | `site/project.html` | 概览 / 历史 / 保护 / 媒体四个标签页、侧栏信息、审核记录、相关项目 |
| AI 问答 | `site/ai.html` | 对话、引用来源、剩余额度、示例问题、回答边界、可发送消息 |
| 登录 | `site/login.html` | 品牌分栏、四类测试账号一键填入、按角色跳转 |
| 注册 | `site/register.html` | 普通用户 / 项目管理者身份、姓名 / 邮箱 / 密码校验、协议确认 |
| 帮助中心 | `site/help.html` | 快速开始、账户、项目、审核归档、AI、角色权限、联系支持、FAQ 搜索 |

### 管理后台（13 页）

| 页面 | 文件 | 覆盖内容 |
|---|---|---|
| 工作台 | `admin/dashboard.html` | 欢迎区、统计卡、最近项目、待办、状态分布、最近动态 |
| 项目库 | `admin/projects.html` | 4 项统计、5 项筛选、批量选择、表格、状态标签、分页、归档弹窗 |
| 新建项目 | `admin/project-new.html` | 步骤条、分组表单、标签、上传区、填写进度、保存 / 提交 |
| 编辑项目 | `admin/project-edit.html` | 驳回意见、三标签页表单、当前状态、审核记录、重新提交 |
| 审核工作台 | `admin/review.html` | 待审队列、材料详情、附件、切换项目、通过 / 驳回弹窗 |
| 归档管理 | `admin/archive.html` | 归档只读提示、归档列表、恢复、修改申请审批 |
| 项目认证 | `admin/certifications.html` | 待审批 / 已通过 / 已驳回、认证材料、审批弹窗 |
| 用户管理 | `admin/users.html` | 四类角色、状态开关、重置密码、新建 / 编辑用户弹窗 |
| 分类体系 | `admin/taxonomy.html` | 地区树、门类表、标签云与标签表、分类维护弹窗 |
| AI 知识库 | `admin/ai.html` | 知识块、向量状态、重建索引、问答日志 |
| 系统运维 | `admin/ops.html` | 系统信息、服务状态、备份、缓存、操作日志、备份弹窗 |
| 个人中心 | `admin/profile.html` | 基本资料、修改密码、登录记录、账号绑定 |
| 通知中心 | `admin/notifications.html` | 通知统计、状态 / 类型筛选、搜索、已读处理、通知偏好、快捷入口 |

### 异常页（2 页）

- `error/403.html`：角色无权限
- `error/404.html`：页面不存在

## 本轮修改

1. **清理演示字样**：页面、脚本、文案中不再出现“演示版”“课程演示”“演示数据”“演示账号”“占位”等字样；登录页改用测试账号说明。
2. **补全帮助中心与通知中心**：新增 `site/help.html` 与 `admin/notifications.html`；顶栏帮助与铃铛、侧栏“支持”分组、页脚均可进入。
3. **调整整体尺寸**：基准字号 14 → 16px，按钮 / 输入 32 → 38px，表格行距与卡片内边距同步上调，侧栏 224 → 240px，顶栏 56 → 60px，公众端内容宽度 1200 → 1280px；100% 缩放下更接近常规 125% 的阅读比例。
4. **调整管理入口**：公众端顶栏移除“管理后台”，入口放到页脚“关于”栏；普通用户浏览界面不再出现后台按钮。
5. **接入接口层**：新增 `assets/js/api.js`，按《系统接口清单 V1.1》覆盖登录、注册、用户、认证、项目、分类、AI、运维、健康检查等接口，并补充通知接口；关键表单与审核 / 认证 / 归档 / 备份等动作已改为调用接口层。

## 设计规范（对齐 Element Plus 默认）

| 项目 | 取值 |
|---|---|
| 主色 | `#409EFF`；深色状态 `#337ECC` |
| 成功 / 警告 / 危险 / 信息 | `#67C23A` / `#E6A23C` / `#F56C6C` / `#909399` |
| 页面背景 / 卡片 | `#F5F7FA` / `#FFFFFF` |
| 主要文字 / 次要文字 / 输入提示 | `#303133` / `#909399` / `#A8ABB2` |
| 边框 | `#DCDFE6` / `#E4E7ED` / `#EBEEF5` |
| 圆角 | 控件 4px，卡片 6px |
| 控件高度 | 默认 38px，大号 44px，小号 28px |
| 基准字号 | 16px；辅助文字 13px |
| 字体 | 系统无衬线：Helvetica Neue / PingFang SC / Microsoft YaHei |
| 后台骨架 | 240px 白色侧栏 + 60px 顶栏 + 浅灰内容区 |
| 响应式 | 1440 / 1100 / 992 / 768 / 520 断点；后台侧栏窄屏变抽屉 |

所有组件都是手写 CSS，没有引入 Vue 或 Element Plus，避免运行环境依赖外网。

## 接口层

`assets/js/api.js` 提供：

- `auth.login / register / logout`
- `me.get / updateProfile / updatePassword / deactivate`
- `users.list / create / update`
- `certifications.mine / list / apply / review`
- `projects.list / get / create / update / status`
- `taxonomy.get / save`
- `ai.chat / rebuild`
- `ops.get / backup`
- `notifications.list / markRead / markAllRead / unreadCount`
- `health()`

模式：

```js
// 默认：mock 模式（后端未就绪，返回与接口一致的数据结构）
window.FEIYI_CONFIG = { mode: "mock", mockDelay: 260 };

// 后端完成后：改为 live 模式
window.FEIYI_CONFIG = {
  mode: "live",
  baseURL: "http://127.0.0.1:8000"
};
```

`live` 模式下，登录 / 注册等表单 POST 会按 Flask 路由提交；其他动作通过 `fetch` 携带 Cookie 与 `X-CSRFToken`，统一处理 `{code, message, data}` 响应与 400/401/403/404/409/429/503 错误。页面列表本身仍由 Jinja2 服务端渲染，JavaScript 接口层主要服务 AI 问答、通知与操作类请求。

## 已实现的交互（原生 JS）

- 公共头部 / 页脚、后台侧栏 / 顶栏按页面注入，保持 23 页一致。
- 后台侧栏折叠（桌面）与抽屉（移动端）；顶栏账号下拉；按登录角色过滤侧栏菜单。
- 标签页切换；弹窗打开 / 关闭 / Esc；`#approveDialog` 这类地址可直达并自动打开弹窗。
- 表格全选 / 单选，选择后出现批量操作条。
- 审核工作台点击左侧项目，右侧标题、地区、门类、摘要、封面同步切换。
- AI 问答调用接口层，返回回答、引用、模式与剩余次数；支持 Enter 发送。
- 登录调用 `auth.login` 并按角色跳转；注册调用 `auth.register`；测试账号一键填入。
- 审核通过 / 驳回、认证审批、项目保存 / 提交、归档恢复、用户创建 / 编辑、分类保存、个人资料、密码修改、备份、索引重建均已接到接口层。
- 通知中心从接口加载，支持筛选、搜索、单条已读与全部已读，未读数同步顶栏与侧栏。
- 帮助中心 FAQ 搜索；顶栏搜索跳转项目库并携带关键词过滤。
- 文件选择、筛选查询、重置、导出等按钮给出 Element 风格消息提示。

## 目录

```
prototype-element/
├── index.html                     # 页面地图（从这里开始）
├── README.md                      # 本文件
├── 演示文档.md                     # 讲解流程、接口映射与角色说明
├── docs/
│   ├── 数据库表设计.xlsx            # V1.1 数据表与字段明细
│   └── 系统接口清单.xlsx            # V1.1 接口、约定与权限矩阵
├── assets/
│   ├── css/
│   │   ├── element.css            # Element 设计令牌与组件
│   │   ├── admin.css              # 后台骨架与业务布局
│   │   └── site.css               # 公众端 / 登录 / 帮助 / 异常页 / 页面地图
│   ├── js/
│   │   ├── api.js                 # 接口层 + mock 数据
│   │   └── app.js                 # 图标、布局注入、弹窗、标签页、AI 对话等
│   └── screenshots/               # 桌面与移动端自检截图
├── site/                          # 7 个公众页面
├── admin/                         # 13 个后台页面
└── error/                         # 403 / 404
```

## 明确未做

- 后端业务实现、真实数据库写入、Flask-Login 会话与 RBAC 服务端校验；前端以 mock 模式运行，接口路径与字段已对齐 V1.1。
- 列表页仍为静态渲染 + 关键词过滤，分页 / 排序 / 多条件组合尚未逐项联动。
- 真实文件上传、图片缩略图、PDF 下载与导出文件生成。
- 通知接口 `GET /api/notifications`、`POST /api/notifications/<id>/read`、`POST /api/notifications/read-all` 为前端新增约定，需在后端接口清单中追加编号。
- 未引入 Axure `.rp` 工程文件。

## 下一步接到 Flask + Jinja2

1. 以 `site/home.html` 为公众端 `base.html`、`admin/dashboard.html` 为后台 `base.html`，把注入的头部 / 侧栏改成 Jinja `include`。
2. CSS 原样复制到 `static/css/`，`api.js` 与 `app.js` 复制到 `static/js/`；不需要 Node 构建。
3. 列表与详情页改用 Jinja2 服务端渲染；`api.js` 保留给 AI 问答、通知和操作类请求。
4. 在 `base.html` 输出 `<meta name="csrf-token" content="{{ csrf_token() }}">`，供 `api.js` 读取。
5. 表单字段已对齐《数据库表设计 V1.1》：`title / summary / region_id / category_id / level / tags / content / history / protection / source_url` 等；状态使用 `draft / pending / published / rejected / archived`，可见性使用 `public / internal`。
6. 通知接口为前端新增约定，后端可按 `review_record`、`certification`、`edit_request`、`audit_log` 聚合生成。

## 重新截图

桌面页可直接使用 Chrome 无头模式；移动端需用 DevTools 协议设置 390 宽（无头 Chrome 的 `--window-size` 最小会按 512 渲染，直接截会裁切）：

```bash
"C:/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 --window-size=1440,900 \
  --screenshot="assets/screenshots/dashboard.png" \
  "file:///C:/Users/StackFF/Desktop/PythonProject/前端模板/prototype-element/admin/dashboard.html"
```

> 数据来自公开名录与项目保护单位资料；接口字段以《数据库表设计 V1.1》《系统接口清单 V1.1》为准。