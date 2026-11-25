# 非遗数字化管理平台







# 非遗数字化管理平台 · 推荐项目结构
```text
非遗数字化管理平台/
├── app/
│   ├── __init__.py                 # 应用工厂、蓝图注册、错误页、CLI
│   ├── config.py                   # 开发 / 测试 / 生产配置
│   ├── extensions.py               # db、login_manager、csrf
│   ├── models.py                   # 14 张表 + 枚举
│   ├── permissions.py              # role_required / can_edit_project
│   ├── cli.py                      # init-db / seed / create-sysadmin
│   │
│   ├── auth.py                     # 注册、登录、退出、/me
│   ├── projects.py                 # 项目列表、详情、新建、编辑、状态
│   ├── admin.py                    # 用户、认证、分类、运维、备份
│   ├── ai.py                       # AI 页面、/api/ai/chat、索引重建
│   ├── main.py                     # 首页、项目库、详情、帮助、健康检查
│   ├── notifications.py            # 通知列表、已读、全部已读
│   │
│   ├── services/
│   │   ├── project_service.py      # 项目 CRUD、筛选、分页
│   │   ├── review_service.py       # 提交 / 通过 / 驳回 / 归档 / 恢复
│   │   ├── rag_service.py          # 切块、检索、Prompt、降级
│   │   └── ops_service.py          # 备份、日志、系统信息
│   │
│   ├── templates/
│   │   ├── base_public.html        # 公众端骨架
│   │   ├── base_admin.html         # 后台骨架
│   │   ├── partials/
│   │   │   ├── public_header.html
│   │   │   ├── public_footer.html
│   │   │   ├── admin_sidebar.html
│   │   │   ├── admin_topbar.html
│   │   │   └── flash.html
│   │   ├── public/
│   │   │   ├── home.html
│   │   │   ├── projects.html
│   │   │   ├── project_detail.html
│   │   │   ├── ai.html
│   │   │   ├── help.html
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── admin/
│   │   │   ├── dashboard.html
│   │   │   ├── projects.html
│   │   │   ├── project_form.html   # 新建 / 编辑共用
│   │   │   ├── review.html
│   │   │   ├── archive.html
│   │   │   ├── certifications.html
│   │   │   ├── users.html
│   │   │   ├── taxonomy.html
│   │   │   ├── ai_knowledge.html
│   │   │   ├── ops.html
│   │   │   ├── profile.html
│   │   │   └── notifications.html
│   │   └── errors/
│   │       ├── 403.html
│   │       ├── 404.html
│   │       └── 500.html
│   │
│   └── static/
│       ├── css/
│       │   ├── element.css         # 设计令牌与通用组件
│       │   ├── site.css            # 公众端 / 登录 / 帮助 / 异常页
│       │   └── admin.css           # 后台骨架与业务布局
│       ├── js/
│       │   ├── api.js              # 接口层
│       │   └── ui.js               # 弹窗、标签页、通知、AI 交互
│       └── img/
│
├── instance/                       # 不提交 Git
│   ├── app.db
│   └── uploads/
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_projects.py
│   ├── test_review.py
│   ├── test_permissions.py
│   └── test_ai.py
│
├── docs/
│   ├── 数据库表设计.xlsx
│   ├── 系统接口清单.xlsx
│   ├── 演示文档.md
│   └── screenshots/
│
├── design/
│   └── prototype-element/          # 当前前端，留作视觉与交互参考
│
├── seed.py                         # 初始化项目、分类与测试账号
├── run.py                          # Flask / Waitress 启动入口
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

