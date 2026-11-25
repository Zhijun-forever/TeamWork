/* =========================================================
   非遗数字化管理平台 · 原型交互
   纯原生 JS，无外部依赖，双击 HTML 即可运行
   ========================================================= */
(function () {
  "use strict";

  /* ---------- 图标库（线性风格，统一 24 viewBox） ---------- */
  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-6h6v6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 2.9-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6"/><path d="M18 14.7c2.1.5 3.5 2.2 3.5 5.3"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    check: '<path d="m5 12 5 5L20 7"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "arrow-left": '<path d="M19 12H5"/><path d="m11 18-6-6 6-6"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8"/><path d="M10.5 20a2 2 0 0 0 3 0"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.6 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
    database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    shield: '<path d="M12 3 20 6v6c0 5-3.4 8.3-8 9-4.6-.7-8-4-8-9V6Z"/><path d="m9 12 2 2 4-4"/>',
    archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
    award: '<circle cx="12" cy="9" r="5"/><path d="m8.5 13.5-2 7L12 18l5.5 2.5-2-7"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
    download: '<path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.5-4L3 10"/><path d="M3 5v5h5"/><path d="M4 13a8 8 0 0 0 14.5 4L21 14"/><path d="M21 19v-5h-5"/>',
    message: '<path d="M21 11.5a8.5 8.5 0 0 1-12.5 7.4L3 20l1.1-5.5A8.5 8.5 0 1 1 21 11.5Z"/>',
    sparkles: '<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z"/><path d="M5 14l.6 1.6L7 16l-1.4.6L5 18l-.6-1.4L3 16l1.4-.4Z"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "map-pin": '<path d="M20 10c0 6-8 11-8 11s-8-5-8-11a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    tag: '<path d="M20.6 13.4 12 22l-9-9V4h9l8.6 8.6a1 1 0 0 1 0 1.4Z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    trash: '<path d="M4 7h16"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/><path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/><path d="M10 11v6M14 11v6"/>',
    more: '<circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "alert-circle": '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16.5h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.5h.01"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "x-circle": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    external: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/>',
    book: '<path d="M12 6c-1.5-2-4-2.5-8-2.5V19c4 0 6.5.5 8 2.5 1.5-2 4-2.5 8-2.5V3.5c-4 0-6.5.5-8 2.5Z"/><path d="M12 6v15.5"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
    server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9"/><path d="m17 6 2 2"/><path d="m14 9 2 2"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    phone: '<path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    filter: '<path d="M3 5h18l-7 8v5l-4 2v-7Z"/>',
    chart: '<path d="M3 20h18"/><path d="M6 20v-6M11 20V8M16 20v-9"/>',
    pie: '<path d="M21 12A9 9 0 1 1 12 3v9Z"/><path d="M16 3.5A9 9 0 0 1 20.5 8H16Z"/>',
    star: '<path d="m12 3 2.7 5.8 6.3.8-4.6 4.4 1.2 6.2L12 17.4l-5.6 2.8 1.2-6.2L3 9.6l6.3-.8Z"/>',
    heart: '<path d="M20.5 5.5a5 5 0 0 0-7 0L12 7l-1.5-1.5a5 5 0 0 0-7 7L12 21l8.5-8.5a5 5 0 0 0 0-7Z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-.9.7-1.5 1.2-1.5 2.5"/><path d="M12 17h.01"/>',
    trend: '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    music: '<path d="M9 18V6l10-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="15" r="2.5"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18c1.7 0 2-1.2 1.3-2-.8-1 .2-2.5 1.7-2.5H18a3 3 0 0 0 3-3A9 9 0 0 0 12 3Z"/><circle cx="7.5" cy="11" r="1" fill="currentColor" stroke="none"/><circle cx="9.5" cy="7" r="1" fill="currentColor" stroke="none"/><circle cx="14" cy="6.5" r="1" fill="currentColor" stroke="none"/>',
    tool: '<path d="M14.5 6.5a4 4 0 0 0-5.4 5.4L3.5 17.5 6.5 20.5l5.6-5.6a4 4 0 0 0 5.4-5.4l-2.8 2.8-2.4-2.4Z"/>',
    flag: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
    smile: '<circle cx="12" cy="12" r="9"/><path d="M8.5 14.5a4.5 4.5 0 0 0 7 0"/><path d="M9 9.5h.01M15 9.5h.01"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
    "file-plus": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M12 12v6M9 15h6"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m21 16-5-5-8 8"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5Z"/>'
  };

  function icon(name, cls) {
    var body = ICONS[name] || ICONS.info;
    return (
      '<span class="el-icon' +
      (cls ? " " + cls : "") +
      '" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
      body +
      "</svg></span>"
    );
  }

  function hydrateIcons(root) {
    (root || document).querySelectorAll("[data-icon]").forEach(function (el) {
      el.innerHTML = icon(el.getAttribute("data-icon"));
      el.classList.add("icon-host");
    });
  }

  /* ---------- 公共头部 / 页脚 ---------- */
  var SITE_NAV = [
    { key: "home", label: "首页", href: "home.html" },
    { key: "projects", label: "项目库", href: "projects.html" },
    { key: "ai", label: "AI 问答", href: "ai.html" },
    { key: "help", label: "帮助中心", href: "help.html" },
    { key: "about", label: "关于平台", href: "home.html#about" }
  ];

  function renderSiteHeader() {
    var host = document.getElementById("site-header");
    if (!host) return;
    var active = host.getAttribute("data-active") || "";
    var nav = SITE_NAV.map(function (item) {
      return (
        '<a href="' +
        item.href +
        '"' +
        (item.key === active ? ' class="is-active"' : "") +
        ">" +
        item.label +
        "</a>"
      );
    }).join("");

    host.className = "site-header";
    host.innerHTML =
      '<div class="site-header__inner">' +
      '<a class="site-brand" href="home.html">' +
      '<span class="site-brand__logo">非</span>' +
      '<span class="site-brand__name">非遗数字化平台</span>' +
      "</a>" +
      '<nav class="site-nav" aria-label="主导航">' +
      nav +
      "</nav>" +
      '<div class="site-header__right">' +
      '<form class="site-search" data-search-form role="search">' +
      '<div class="el-input"><span class="el-input__prefix">' +
      icon("search", "el-icon--sm") +
      '</span><input class="el-input__inner" type="search" name="q" placeholder="搜索项目、地区、门类" aria-label="搜索"></div>' +
      "</form>" +
      '<a class="el-button" href="login.html">登录</a>' +
      '<a class="el-button el-button--primary" href="register.html">注册</a>' +
      "</div>" +
      "</div>";
  }

  function renderSiteFooter() {
    var host = document.getElementById("site-footer");
    if (!host) return;
    host.className = "site-footer";
    host.innerHTML =
      '<div class="site-footer__inner">' +
      '<div class="site-footer__brand">' +
      '<div class="site-brand"><span class="site-brand__logo">非</span>' +
      '<span class="site-brand__name">非遗数字化平台</span></div>' +
      "<p>面向省市级非遗保护中心、项目保护单位与公众的轻量管理平台。项目从创建到归档全程可追溯，公众可按地区、门类、标签检索并提问。</p>" +
      "</div>" +
      '<div class="site-footer__col"><h4>浏览</h4>' +
      '<a href="projects.html">项目库</a><a href="projects.html">十大门类</a>' +
      '<a href="projects.html">按地区浏览</a><a href="ai.html">AI 问答</a></div>' +
      '<div class="site-footer__col"><h4>参与</h4>' +
      '<a href="register.html">注册账号</a><a href="login.html">项目管理者登录</a>' +
      '<a href="register.html">申请项目认证</a><a href="home.html#about">平台说明</a></div>' +
      '<div class="site-footer__col"><h4>关于</h4>' +
      '<a href="home.html#about">关于项目</a><a href="../admin/dashboard.html">管理后台</a>' +
      '<a href="../index.html">页面地图</a><a href="help.html">帮助中心</a></div>' +
      "</div>" +
      '<div class="site-footer__bottom">' +
      "<span>© 2026 非遗数字化管理平台</span>" +
      "<span>数据来自公开名录与项目保护单位资料</span>" +
      "</div>";
  }

  /* ---------- 管理后台骨架 ---------- */
  var ADMIN_NAV = [
    {
      group: "概览",
      items: [{ key: "dashboard", label: "工作台", icon: "home", href: "dashboard.html", roles: ["sysadmin", "admin", "manager"] }]
    },
    {
      group: "项目管理",
      items: [
        { key: "projects", label: "项目库", icon: "folder", href: "projects.html", roles: ["manager", "admin", "sysadmin"] },
        { key: "new", label: "新建项目", icon: "file-plus", href: "project-new.html", roles: ["manager", "admin", "sysadmin"] },
        { key: "review", label: "待审核", icon: "check-circle", href: "review.html", count: 6, roles: ["admin", "sysadmin"] },
        { key: "archive", label: "归档管理", icon: "archive", href: "archive.html", roles: ["admin", "sysadmin"] }
      ]
    },
    {
      group: "认证与分类",
      items: [
        { key: "certifications", label: "项目认证", icon: "award", href: "certifications.html", count: 3, roles: ["admin", "sysadmin"] },
        { key: "taxonomy", label: "分类体系", icon: "layers", href: "taxonomy.html", roles: ["admin", "sysadmin"] }
      ]
    },
    {
      group: "AI 知识库",
      items: [
        { key: "ai", label: "知识库", icon: "sparkles", href: "ai.html", roles: ["admin", "sysadmin"] },
        { key: "chatlog", label: "问答日志", icon: "message", href: "ai.html#logs", roles: ["admin", "sysadmin"] }
      ]
    },
    {
      group: "系统",
      items: [
        { key: "users", label: "用户管理", icon: "users", href: "users.html", roles: ["admin", "sysadmin"] },
        { key: "ops", label: "系统运维", icon: "server", href: "ops.html", roles: ["sysadmin"] },
        { key: "profile", label: "个人中心", icon: "user", href: "profile.html", roles: ["sysadmin", "admin", "manager"] }
      ]
    },
    {
      group: "支持",
      items: [
        { key: "notifications", label: "通知中心", icon: "bell", href: "notifications.html", count: 3, roles: ["sysadmin", "admin", "manager"] },
        { key: "help", label: "帮助中心", icon: "help", href: "../site/help.html", roles: ["sysadmin", "admin", "manager"] }
      ]
    }
  ];

  function renderAdminAside() {
    var host = document.getElementById("admin-aside");
    if (!host) return;
    var active = host.getAttribute("data-active") || "";
    var html =
      '<a class="admin-brand" href="dashboard.html">' +
      '<span class="admin-brand__logo">非</span>' +
      '<span class="admin-brand__text">' +
      '<span class="admin-brand__name">非遗数字化平台</span>' +
      '<span class="admin-brand__sub">MANAGEMENT CONSOLE</span>' +
      "</span></a>" +
      '<nav class="admin-menu" aria-label="后台导航">';

    var sessionRole = "sysadmin";
    try {
      var storedSession = JSON.parse(window.sessionStorage.getItem("feiyi.session") || "null");
      if (storedSession && storedSession.role) sessionRole = storedSession.role;
    } catch (e) {}

    ADMIN_NAV.forEach(function (group) {
      var visibleItems = group.items.filter(function (item) {
        return !item.roles || item.roles.indexOf(sessionRole) !== -1;
      });
      if (!visibleItems.length) return;
      html += '<div class="nav-group-title">' + group.group + "</div>";
      visibleItems.forEach(function (item) {
        html +=
          '<a class="nav-item' +
          (item.key === active ? " is-active" : "") +
          '" href="' +
          item.href +
          '">' +
          icon(item.icon) +
          '<span class="nav-item__text">' +
          item.label +
          "</span>" +
          (item.count ? '<span class="count-badge">' + item.count + "</span>" : "") +
          "</a>";
      });
    });

    html +=
      "</nav>" +
      '<div class="aside-foot"><span class="status-dot"></span><span>系统运行正常 · v1.1</span></div>';
    host.className = "admin-aside";
    host.innerHTML = html;
  }

  function renderAdminTopbar() {
    var host = document.getElementById("admin-topbar");
    if (!host) return;
    var title = host.getAttribute("data-title") || "工作台";
    var crumb = host.getAttribute("data-crumb") || "首页 / 工作台";
    var parts = crumb.split("/").map(function (s) { return s.trim(); }).filter(Boolean);
    var crumbHtml = parts
      .map(function (part, i) {
        var isLast = i === parts.length - 1;
        return (
          '<span class="el-breadcrumb__item' +
          (isLast ? " is-last" : "") +
          '">' +
          (isLast ? part : '<a href="javascript:;">' + part + "</a>") +
          '</span><span class="el-breadcrumb__separator">/</span>'
        );
      })
      .join("")
      .replace(/<span class="el-breadcrumb__separator">\/<\/span>$/, "");

    host.className = "admin-topbar";
    host.setAttribute("data-title", title);
    host.innerHTML =
      '<button class="topbar-toggle" type="button" data-action="toggle-aside" aria-label="展开或收起侧栏">' +
      icon("menu", "el-icon--lg") +
      "</button>" +
      '<div class="topbar-breadcrumb"><div class="el-breadcrumb">' +
      crumbHtml +
      "</div></div>" +
      '<div class="topbar-actions">' +
      '<form class="topbar-search" data-search-form role="search">' +
      '<div class="el-input"><span class="el-input__prefix">' +
      icon("search", "el-icon--sm") +
      '</span><input class="el-input__inner" type="search" placeholder="搜索项目、用户、知识块" aria-label="全局搜索"></div>' +
      "</form>" +
      '<a class="icon-btn icon-btn--optional" href="../site/help.html" target="_blank" rel="noopener" aria-label="帮助中心">' +
      icon("help", "el-icon--lg") +
      "</a>" +
      '<a class="icon-btn" href="notifications.html" aria-label="通知中心">' +
      icon("bell", "el-icon--lg") +
      '<span class="count-badge" data-notify-badge>3</span></a>' +
      '<span class="topbar-divider"></span>' +
      '<div class="el-dropdown" data-dropdown>' +
      '<button class="topbar-user" type="button" data-dropdown-toggle aria-haspopup="menu" aria-expanded="false">' +
      '<span class="el-avatar el-avatar--primary">管</span>' +
      '<span class="topbar-user__text"><span class="topbar-user__name">admin01</span>' +
      '<span class="topbar-user__role">管理员</span></span>' +
      icon("chevron-down", "el-icon--sm") +
      "</button>" +
      '<div class="el-dropdown__menu" role="menu">' +
      '<a class="el-dropdown__item" href="profile.html">' + icon("user", "el-icon--sm") + "个人中心</a>" +
      '<a class="el-dropdown__item" href="profile.html">' + icon("settings", "el-icon--sm") + "账号设置</a>" +
      '<a class="el-dropdown__item" href="../site/home.html">' + icon("globe", "el-icon--sm") + "前往公众端</a>" +
      '<div class="el-dropdown__divider"></div>' +
      '<a class="el-dropdown__item is-danger" href="../site/login.html" data-logout>' + icon("logout", "el-icon--sm") + "退出登录</a>" +
      "</div></div>" +
      "</div>";

    var shell = document.querySelector(".admin-shell");
    if (shell && !shell.querySelector(".admin-aside__mask")) {
      var mask = document.createElement("div");
      mask.className = "admin-aside__mask";
      mask.setAttribute("data-action", "close-aside");
      shell.insertBefore(mask, shell.firstChild);
    }
  }

  /* ---------- 消息提示 ---------- */
  function toast(message, type) {
    var box = document.querySelector(".el-message-container");
    if (!box) {
      box = document.createElement("div");
      box.className = "el-message-container";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    var map = {
      success: { cls: "el-message--success", icon: "check-circle" },
      warning: { cls: "el-message--warning", icon: "alert-circle" },
      error: { cls: "el-message--error", icon: "x-circle" },
      info: { cls: "", icon: "info" }
    };
    var meta = map[type] || map.info;
    var el = document.createElement("div");
    el.className = "el-message " + meta.cls;
    el.innerHTML = icon(meta.icon, "el-icon--sm") + "<span>" + message + "</span>";
    box.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transform = "translateY(-6px)";
      el.style.transition = "all .2s ease";
      setTimeout(function () { el.remove(); }, 220);
    }, 2200);
  }

  /* ---------- 弹窗 ---------- */
  function openDialog(id) {
    var dlg = document.getElementById(id);
    if (!dlg) return;
    dlg.classList.add("is-open");
    dlg.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    var first = dlg.querySelector("input, textarea, select, button");
    if (first) setTimeout(function () { first.focus(); }, 60);
  }

  function closeDialog(dlg) {
    if (!dlg) return;
    dlg.classList.remove("is-open");
    dlg.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function closeAllDialogs() {
    document.querySelectorAll(".el-dialog.is-open").forEach(closeDialog);
  }

  /* ---------- 标签页 ---------- */
  function activateTab(group, key) {
    var tabs = group.querySelectorAll("[data-tab]");
    var panels = group.querySelectorAll("[data-tab-panel]");
    tabs.forEach(function (btn) {
      var on = btn.getAttribute("data-tab") === key;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach(function (panel) {
      panel.classList.toggle("is-active", panel.getAttribute("data-tab-panel") === key);
    });
  }

  /* ---------- 表格多选 ---------- */
  function refreshSelection() {
    var checks = Array.prototype.slice.call(document.querySelectorAll("[data-row-check]"));
    var selected = checks.filter(function (c) { return c.checked; });
    document.querySelectorAll("[data-selected-count]").forEach(function (el) {
      el.textContent = selected.length;
    });
    document.querySelectorAll(".selection-bar").forEach(function (bar) {
      bar.classList.toggle("is-visible", selected.length > 0);
    });
    var all = document.querySelector("[data-select-all]");
    if (all && checks.length) {
      all.checked = selected.length === checks.length;
      all.indeterminate = selected.length > 0 && selected.length < checks.length;
    }
  }

  /* ---------- 审核工作台 ---------- */
  function bindReviewList() {
    var items = document.querySelectorAll("[data-review-item]");
    if (!items.length) return;
    items.forEach(function (item) {
      item.addEventListener("click", function () {
        items.forEach(function (i) { i.classList.remove("is-active"); });
        item.classList.add("is-active");
        var data = {
          title: item.getAttribute("data-title"),
          owner: item.getAttribute("data-owner"),
          region: item.getAttribute("data-region"),
          category: item.getAttribute("data-category"),
          date: item.getAttribute("data-date"),
          summary: item.getAttribute("data-summary")
        };
        Object.keys(data).forEach(function (key) {
          document.querySelectorAll('[data-review-' + key + "]").forEach(function (el) {
            el.textContent = data[key] || "";
          });
        });
        var cover = document.querySelector("[data-review-cover]");
        if (cover) {
          cover.textContent = (data.title || "").charAt(0);
          cover.setAttribute("data-tone", item.getAttribute("data-tone") || "");
        }
        var detail = document.querySelector(".review-detail");
        if (detail && window.scrollY > 300) {
          detail.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  /* ---------- AI 问答 ---------- */
  function bindChat() {
    var form = document.getElementById("chatForm");
    if (!form) return;
    var input = form.querySelector("textarea");
    var body = document.querySelector(".chat-body");
    var quotaEl = document.querySelector("[data-chat-quota]");
    var remaining = 12;

    function sourcesHtml(sources) {
      if (!sources || !sources.length) return "";
      return (
        '<div class="chat-sources"><div class="chat-sources__title">' +
        icon("link", "el-icon--sm") +
        "引用来源（" + sources.length + "）</div>" +
        sources
          .map(function (s, i) {
            var href = s.project_id ? "project.html?id=" + s.project_id : "project.html";
            return (
              '<div class="chat-source"><span class="chat-source__index">' +
              (i + 1) +
              '</span><a href="' + href + '">' +
              escapeHtml(s.title || "项目详情") +
              '</a><span class="chat-source__meta">' +
              escapeHtml(s.category || s.meta || "") +
              "</span></div>"
            );
          })
          .join("") +
        "</div>"
      );
    }

    function appendUser(text) {
      var el = document.createElement("div");
      el.className = "chat-msg chat-msg--user";
      el.innerHTML =
        '<span class="chat-msg__avatar chat-msg__avatar--user">我</span>' +
        '<div class="chat-msg__content"><div class="chat-bubble">' +
        escapeHtml(text) +
        '</div><div class="chat-msg__time">刚刚</div></div>';
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
    }

    function appendAi(html, sources, modeText) {
      var el = document.createElement("div");
      el.className = "chat-msg";
      el.innerHTML =
        '<span class="chat-msg__avatar chat-msg__avatar--ai">' + icon("sparkles", "el-icon--sm") + "</span>" +
        '<div class="chat-msg__content"><div class="chat-bubble">' +
        html +
        '</div><div class="chat-msg__time">刚刚 · ' +
        (modeText ? escapeHtml(modeText) + " · " : "") +
        "回答仅供参考</div>" +
        sourcesHtml(sources) +
        "</div>";
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
    }

    function escapeHtml(str) {
      return String(str).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    }

    function textToHtml(text) {
      return String(text || "")
        .split(/\n+/)
        .filter(function (p) { return p.trim(); })
        .map(function (p) { return "<p>" + escapeHtml(p.trim()) + "</p>"; })
        .join("");
    }

    var sending = false;

    function send(text) {
      text = (text || "").trim();
      if (!text) {
        toast("请输入问题", "warning");
        return;
      }
      if (remaining <= 0) {
        toast("今日提问次数已用完（15 次 / 天）", "error");
        return;
      }
      if (sending) return;
      sending = true;
      appendUser(text);
      input.value = "";
      var api = window.FeiyiAPI;
      var request = api ? api.ai.chat(text) : Promise.reject(new Error("问答服务暂不可用"));
      request.then(function (res) {
        remaining = typeof res.remaining === "number" ? res.remaining : Math.max(0, remaining - 1);
        if (quotaEl) quotaEl.textContent = remaining;
        var mode = res.mode || "rag";
        var modeText = api && api.maps && api.maps.aiMode ? api.maps.aiMode[mode] : "";
        appendAi(textToHtml(res.answer), res.sources || [], modeText);
      }).catch(function (err) {
        toast((err && err.message) || "问答服务暂不可用，请稍后重试", "error");
        if (err && err.status === 401) {
          window.setTimeout(function () { window.location.href = "login.html"; }, 900);
        }
      }).finally(function () {
        sending = false;
      });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      send(input.value);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send(input.value);
      }
    });

    document.querySelectorAll("[data-chat-suggest]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        send(btn.textContent.trim());
      });
    });
  }

  /* ---------- 通用工具 ---------- */
  function escapeText(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fieldValue(selector, fallback) {
    var el = document.querySelector(selector);
    return el ? el.value : (fallback || "");
  }

  function apiFail(err) {
    toast((err && err.message) || "操作失败，请稍后重试", "error");
  }

  function closeDialogOf(el) {
    var dlg = el.closest(".el-dialog");
    if (dlg) closeDialog(dlg);
  }

  /* ---------- 通知中心 ---------- */
  function updateNotifyBadges(n) {
    document.querySelectorAll("[data-notify-badge]").forEach(function (badge) {
      badge.textContent = n;
      badge.classList.toggle("hidden", n === 0);
    });
    document.querySelectorAll('.nav-item[href="notifications.html"] .count-badge').forEach(function (badge) {
      badge.textContent = n;
      badge.classList.toggle("hidden", n === 0);
    });
  }

  function initNotifications() {
    var list = document.getElementById("notificationList");
    if (!list || !window.FeiyiAPI) return;
    var api = window.FeiyiAPI;
    var state = { status: "all", type: "", q: "" };

    function notifyIcon(type) {
      return { review: "check-circle", certification: "award", project: "folder", system: "server" }[type] || "bell";
    }

    function applyFilter(btn) {
      state.status = btn.getAttribute("data-filter") || "all";
      state.type = btn.getAttribute("data-type") || "";
      document.querySelectorAll("[data-notify-filter]").forEach(function (b) {
        b.classList.toggle("is-active", b === btn);
      });
      load();
    }

    function load() {
      var query = {};
      if (state.status === "unread") query.status = "unread";
      if (state.status === "read") query.status = "read";
      if (state.type) query.type = state.type;
      if (state.q) query.q = state.q;
      list.innerHTML = '<div class="el-empty"><div class="el-empty__icon">' + icon("refresh") + '</div><div class="el-empty__title">正在加载通知…</div></div>';
      api.notifications.list(query).then(function (res) {
        var items = res.items || [];
        var unread = typeof res.unread === "number" ? res.unread : 0;
        document.querySelectorAll("[data-notify-unread]").forEach(function (el) { el.textContent = unread; });
        document.querySelectorAll("[data-notify-total]").forEach(function (el) { el.textContent = res.total || items.length; });
        updateNotifyBadges(unread);
        if (!items.length) {
          list.innerHTML = '<div class="el-empty"><div class="el-empty__icon">' + icon("bell") + '</div><div class="el-empty__title">暂无通知</div><div class="el-empty__desc">当前筛选条件下没有可显示的通知。</div></div>';
          return;
        }
        list.innerHTML = items.map(function (n) {
          return (
            '<article class="notify-item' + (n.read ? "" : " is-unread") + '" data-notification-id="' + n.id + '">' +
            '<span class="notify-item__icon notify-item__icon--' + escapeText(n.type) + '">' + icon(notifyIcon(n.type)) + '</span>' +
            '<div class="notify-item__body">' +
            '<div class="notify-item__head"><span class="notify-item__title">' + escapeText(n.title) + '</span>' +
            (n.read ? "" : '<span class="notify-item__dot" aria-label="未读"></span>') + '</div>' +
            '<p class="notify-item__desc">' + escapeText(n.content) + '</p>' +
            '<div class="notify-item__meta"><span class="el-tag el-tag--plain">' + escapeText((api.maps.notifyType && api.maps.notifyType[n.type]) || "系统") + '</span>' +
            '<span>' + escapeText(n.created_at) + '</span>' +
            '<a href="' + escapeText(n.link || "notifications.html") + '">查看详情</a>' +
            (n.read ? "" : '<button type="button" data-notify-read="' + n.id + '">标为已读</button>') +
            '</div></div></article>'
          );
        }).join("");
      }).catch(function (err) {
        list.innerHTML = '<div class="el-empty"><div class="el-empty__icon">' + icon("alert-circle") + '</div><div class="el-empty__title">通知加载失败</div><div class="el-empty__desc">' + escapeText(err.message || "请稍后重试") + '</div></div>';
      });
    }

    document.querySelectorAll("[data-notify-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () { applyFilter(btn); });
    });

    var search = document.getElementById("notifySearch");
    if (search) {
      search.addEventListener("input", function () {
        state.q = search.value.trim();
        window.clearTimeout(search._timer);
        search._timer = window.setTimeout(load, 220);
      });
    }

    document.querySelectorAll("[data-notify-read-all]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        api.notifications.markAllRead().then(function () {
          toast("全部通知已标为已读", "success");
          load();
        }).catch(apiFail);
      });
    });

    list.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-notify-read]");
      if (!btn) return;
      api.notifications.markRead(btn.getAttribute("data-notify-read")).then(function () {
        toast("已标为已读", "success");
        load();
      }).catch(apiFail);
    });

    load();
  }

  /* ---------- 帮助中心 FAQ 搜索 ---------- */
  function initHelpSearch() {
    var input = document.querySelector("[data-help-search]");
    if (!input) return;
    var items = document.querySelectorAll("[data-help-item]");
    var empty = document.querySelector("[data-help-empty]");
    var count = document.querySelector("[data-help-count]");
    function run() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      items.forEach(function (item) {
        var hit = !q || item.textContent.toLowerCase().indexOf(q) !== -1;
        item.classList.toggle("hidden", !hit);
        if (hit) shown += 1;
      });
      if (empty) empty.classList.toggle("hidden", shown !== 0);
      if (count) count.textContent = shown;
    }
    input.addEventListener("input", run);
    run();
  }

  /* ---------- 会话与通知徽标 ---------- */
  function hydrateSession() {
    var api = window.FeiyiAPI;
    if (!api || api.config.mode !== "mock") return;
    api.me.get().then(function (user) {
      var name = document.querySelector(".topbar-user__name");
      var role = document.querySelector(".topbar-user__role");
      var avatar = document.querySelector(".topbar-user .el-avatar");
      if (name) name.textContent = user.username;
      if (role) role.textContent = (api.maps.role && api.maps.role[user.role]) || user.role;
      if (avatar) avatar.textContent = (user.real_name || user.username).charAt(0);
      var welcome = document.querySelector(".welcome-card__title");
      if (welcome) welcome.textContent = "欢迎回来，" + user.username;
    }).catch(function () {});
    api.notifications.unreadCount().then(function (n) {
      updateNotifyBadges(n);
    }).catch(function () {});
  }

  /* ---------- 接口动作绑定 ---------- */
  function buildProjectPayload() {
    var visibility = document.querySelector('input[name="visibility"]:checked');
    var tags = Array.prototype.map.call(document.querySelectorAll("#tags ~ .el-tag, .form-main .el-tag"), function (el) {
      return el.textContent.replace("✕", "").trim();
    }).filter(Boolean);
    return {
      title: fieldValue("#title"),
      summary: fieldValue("#summary"),
      region_name: [fieldValue("#province"), fieldValue("#city")].filter(Boolean).join(" / "),
      category_name: fieldValue("#category"),
      level: fieldValue("#level"),
      content: fieldValue("#content"),
      history: fieldValue("#history"),
      protection: fieldValue("#protection"),
      source_url: fieldValue("#source"),
      visibility: visibility ? visibility.value : "",
      tags: tags
    };
  }

  function bindApiActions() {
    document.addEventListener("click", function (e) {
      var el = e.target.closest("[data-api]");
      if (!el) return;
      var type = el.getAttribute("data-api");
      var api = window.FeiyiAPI;
      if (!api) {
        toast("接口层未加载，请刷新页面", "error");
        return;
      }
      e.preventDefault();

      if (type === "project-status") {
        var id = el.getAttribute("data-id");
        if (!id && el.closest("tr")) id = el.closest("tr").getAttribute("data-record-id");
        if (!id) {
          var active = document.querySelector(".review-item.is-active");
          id = active ? active.getAttribute("data-project-id") : "";
        }
        var action = el.getAttribute("data-action");
        var commentSel = el.getAttribute("data-comment");
        var comment = commentSel ? fieldValue(commentSel) : (el.getAttribute("data-comment-text") || "");
        if (action === "reject" && !String(comment).trim()) {
          toast("驳回必须填写意见", "warning");
          return;
        }
        var success = {
          submit: "已提交审核", approve: "审核通过，项目已发布",
          reject: "已驳回，意见已通知项目管理者", archive: "项目已归档",
          restore: "项目已恢复为已发布", request_edit: "修改申请已提交"
        }[action] || "操作已完成";
        api.projects.status(id, action, comment).then(function () {
          toast(success, "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "cert-review") {
        var certId = el.getAttribute("data-id");
        var certAction = el.getAttribute("data-action");
        var certComment = fieldValue("#certNote");
        api.certifications.review(certId, certAction, certComment).then(function () {
          toast(certAction === "approve" ? "认证已通过" : "认证申请已驳回", "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "user-save") {
        var userId = el.getAttribute("data-id");
        var userPayload = {
          username: fieldValue("#newUser"),
          real_name: fieldValue("#newName"),
          role: fieldValue("#newRole"),
          email: fieldValue("#newEmail"),
          phone: fieldValue("#newPhone"),
          password: fieldValue("#newPassword")
        };
        var req = userId ? api.users.update(userId, userPayload) : api.users.create(userPayload);
        req.then(function () {
          toast(userId ? "用户资料已更新" : "用户已创建", "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "taxonomy-save") {
        api.taxonomy.save({
          type: fieldValue("#taxType"), action: "create", name: fieldValue("#taxName"),
          parent_id: fieldValue("#taxParent"), level: fieldValue("#taxLevel"),
          sort_order: fieldValue("#taxSort"), description: fieldValue("#taxDesc")
        }).then(function () {
          toast("分类节点已保存", "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "profile-save") {
        api.me.updateProfile({
          real_name: fieldValue("#pName"),
          email: fieldValue("#pEmail"),
          phone: fieldValue("#pPhone"),
          organization: fieldValue("#pOrg")
        }).then(function () {
          toast("个人资料已保存", "success");
        }).catch(apiFail);
        return;
      }

      if (type === "profile-password") {
        if (fieldValue("#newPwd") !== fieldValue("#newPwd2")) {
          toast("两次输入的新密码不一致", "error");
          return;
        }
        api.me.updatePassword({
          old_password: fieldValue("#oldPwd"),
          new_password: fieldValue("#newPwd")
        }).then(function () {
          toast("密码已更新，请重新登录", "success");
        }).catch(apiFail);
        return;
      }

      if (type === "project-save") {
        var projectId = el.getAttribute("data-project-id");
        var mode = el.getAttribute("data-mode") || "draft";
        var payload = buildProjectPayload();
        var save = projectId ? api.projects.update(projectId, payload) : api.projects.create(payload);
        save.then(function (res) {
          var pid = projectId || (res.project && res.project.id);
          if (mode === "submit" && pid) return api.projects.status(pid, "submit");
          return res;
        }).then(function () {
          toast(mode === "submit" ? "已提交审核，等待管理员处理" : "已保存", "success");
          window.setTimeout(function () { window.location.href = "projects.html"; }, 700);
        }).catch(apiFail);
        return;
      }

      if (type === "backup") {
        if (api.config.mode === "live") {
          window.location.href = (api.config.baseURL || "") + "/admin/backup";
          return;
        }
        api.ops.backup().then(function (res) {
          toast("备份文件已生成：" + (res.filename || "app-backup.zip"), "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "ai-rebuild") {
        api.ai.rebuild().then(function (res) {
          toast("索引重建完成：" + res.projects + " 个项目、" + res.chunks + " 个知识块", "success");
          closeDialogOf(el);
        }).catch(apiFail);
        return;
      }

      if (type === "notification-read-all") {
        api.notifications.markAllRead().then(function () {
          toast("全部通知已标为已读", "success");
          document.querySelectorAll(".notify-item").forEach(function (item) {
            item.classList.remove("is-unread");
            var dot = item.querySelector(".notify-item__dot");
            if (dot) dot.remove();
            var btn = item.querySelector("[data-notify-read]");
            if (btn) btn.remove();
          });
          document.querySelectorAll("[data-notify-unread]").forEach(function (el) { el.textContent = "0"; });
          updateNotifyBadges(0);
        }).catch(apiFail);
        return;
      }

      toast("该操作暂未接入", "warning");
    });
  }

  /* ---------- 列表关键词过滤（来自顶栏搜索 ?q=） ---------- */
  function initQueryFilter() {
    var params = new URLSearchParams(window.location.search);
    var q = (params.get("q") || "").trim();
    var input = document.getElementById("q");
    if (q && input) input.value = q;
    if (!q) return;
    var keyword = q.toLowerCase();
    var cards = document.querySelectorAll(".project-grid .p-card");
    var rows = document.querySelectorAll(".table-card tbody tr");
    cards.forEach(function (card) {
      card.classList.toggle("hidden", card.textContent.toLowerCase().indexOf(keyword) === -1);
    });
    rows.forEach(function (row) {
      if (row.querySelector("[data-row-check]") || row.querySelector("td")) {
        row.classList.toggle("hidden", row.textContent.toLowerCase().indexOf(keyword) === -1);
      }
    });
  }

  /* ---------- 初始化 ---------- */
  function init() {
    renderSiteHeader();
    renderSiteFooter();
    renderAdminAside();
    renderAdminTopbar();
    hydrateIcons(document);

    // 站点搜索：跳转到项目库并携带关键词
    document.querySelectorAll("[data-search-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var q = form.querySelector("input");
        if (!q || !q.value.trim()) {
          toast("请输入搜索关键词", "warning");
          return;
        }
        window.location.href = "projects.html?q=" + encodeURIComponent(q.value.trim());
      });
    });

    // 退出登录
    document.querySelectorAll("[data-logout]").forEach(function (link) {
      link.addEventListener("click", function (e) {
        if (!window.FeiyiAPI) return;
        e.preventDefault();
        window.FeiyiAPI.auth.logout().then(function () {
          window.location.href = "../site/login.html";
        }).catch(function () {
          window.location.href = "../site/login.html";
        });
      });
    });

    // 通用 toast
    document.addEventListener("click", function (e) {
      var toastEl = e.target.closest("[data-toast]");
      if (toastEl) {
        e.preventDefault();
        toast(toastEl.getAttribute("data-toast"), toastEl.getAttribute("data-toast-type") || "info");
      }
    });

    // 侧栏展开 / 收起
    document.addEventListener("click", function (e) {
      if (!e.target.closest('[data-action="toggle-aside"]')) return;
      var shell = document.querySelector(".admin-shell");
      if (!shell) return;
      if (window.innerWidth <= 768) {
        shell.classList.toggle("is-mobile-open");
      } else {
        shell.classList.toggle("is-collapsed");
      }
    });

    document.addEventListener("click", function (e) {
      if (e.target.closest('[data-action="close-aside"]')) {
        var shell = document.querySelector(".admin-shell");
        if (shell) shell.classList.remove("is-mobile-open");
      }
    });

    // 下拉菜单
    document.addEventListener("click", function (e) {
      var toggle = e.target.closest("[data-dropdown-toggle]");
      var dropdowns = document.querySelectorAll(".el-dropdown");
      if (toggle) {
        var parent = toggle.closest(".el-dropdown");
        var wasOpen = parent.classList.contains("is-open");
        dropdowns.forEach(function (d) { d.classList.remove("is-open"); });
        parent.classList.toggle("is-open", !wasOpen);
        toggle.setAttribute("aria-expanded", !wasOpen ? "true" : "false");
        return;
      }
      if (!e.target.closest(".el-dropdown__menu")) {
        dropdowns.forEach(function (d) { d.classList.remove("is-open"); });
      }
    });

    // 弹窗
    document.querySelectorAll("[data-dialog-open]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dialogId = btn.getAttribute("data-dialog-open");
        var recordId = btn.getAttribute("data-record-id");
        if (!recordId && btn.closest("tr")) recordId = btn.closest("tr").getAttribute("data-record-id");
        var dlg = document.getElementById(dialogId);
        if (dlg && recordId) {
          dlg.querySelectorAll("[data-api]").forEach(function (target) {
            target.setAttribute("data-id", recordId);
          });
        }
        if (dialogId === "userDialog" && dlg) {
          var titleEl = dlg.querySelector("#userDialogTitle");
          var confirmBtn = dlg.querySelector('[data-api="user-save"]');
          var newUser = dlg.querySelector("#newUser");
          var newName = dlg.querySelector("#newName");
          var newEmail = dlg.querySelector("#newEmail");
          var newPhone = dlg.querySelector("#newPhone");
          var newRole = dlg.querySelector("#newRole");
          var row = btn.closest("tr");
          if (row && recordId) {
            var username = row.querySelector(".cell-title") ? row.querySelector(".cell-title").textContent.trim() : "";
            var sub = row.querySelector(".cell-sub") ? row.querySelector(".cell-sub").textContent.trim() : "";
            var emailMatch = row.textContent.match(/[\w.+-]+@[\w.-]+/);
            var roleTag = row.querySelector(".el-tag");
            if (titleEl) titleEl.textContent = "编辑用户";
            if (confirmBtn) confirmBtn.textContent = "保存修改";
            if (newUser) { newUser.value = username; newUser.readOnly = true; }
            if (newName) newName.value = sub.split("·")[0].trim();
            if (newEmail) newEmail.value = emailMatch ? emailMatch[0] : "";
            if (newPhone) newPhone.value = "";
            if (newRole && roleTag) {
              var roleText = roleTag.textContent.trim();
              Array.prototype.forEach.call(newRole.options, function (opt) {
                if (opt.text.indexOf(roleText) !== -1) newRole.value = opt.value;
              });
            }
          } else {
            if (titleEl) titleEl.textContent = "新建用户";
            if (confirmBtn) confirmBtn.textContent = "确认创建";
            if (newUser) { newUser.value = ""; newUser.readOnly = false; }
            if (newName) newName.value = "";
            if (newEmail) newEmail.value = "";
            if (newPhone) newPhone.value = "";
            if (newRole) newRole.selectedIndex = 0;
          }
        }
        openDialog(dialogId);
      });
    });

    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-dialog-close]")) {
        closeDialog(e.target.closest(".el-dialog"));
        return;
      }
      if (e.target.classList.contains("el-dialog__mask")) {
        closeDialog(e.target.closest(".el-dialog"));
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeAllDialogs();
        document.querySelectorAll(".el-dropdown.is-open").forEach(function (d) {
          d.classList.remove("is-open");
        });
      }
    });

    // 弹窗内确认按钮
    document.querySelectorAll("[data-dialog-confirm]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-dialog-confirm") || "操作成功";
        toast(text, "success");
        closeDialog(btn.closest(".el-dialog"));
      });
    });

    // 标签页
    document.querySelectorAll("[data-tabs]").forEach(function (group) {
      group.querySelectorAll("[data-tab]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          activateTab(group, btn.getAttribute("data-tab"));
        });
      });
    });

    // 通过地址栏 hash 激活标签页（如 ai.html#logs）或打开弹窗（如 review.html#approveDialog）
    if (location.hash) {
      var key = location.hash.replace("#", "");
      document.querySelectorAll("[data-tabs]").forEach(function (group) {
        if (group.querySelector('[data-tab="' + key + '"]')) {
          activateTab(group, key);
        }
      });
      var hashTarget = document.getElementById(key);
      if (hashTarget && hashTarget.classList.contains("el-dialog")) {
        openDialog(key);
      }
    }

    // 多选表格
    document.querySelectorAll("[data-select-all]").forEach(function (all) {
      all.addEventListener("change", function () {
        document.querySelectorAll("[data-row-check]").forEach(function (c) {
          c.checked = all.checked;
        });
        refreshSelection();
      });
    });

    document.querySelectorAll("[data-row-check]").forEach(function (check) {
      check.addEventListener("change", refreshSelection);
    });
    refreshSelection();

    // 密码显示切换
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var input = document.querySelector(btn.getAttribute("data-toggle-password"));
        if (!input) return;
        input.type = input.type === "password" ? "text" : "password";
        toast(input.type === "text" ? "密码已显示" : "密码已隐藏", "info");
      });
    });

    // 角色快捷填入
    document.querySelectorAll("[data-demo-user]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var user = btn.getAttribute("data-demo-user");
        var account = document.getElementById("loginAccount");
        var password = document.getElementById("loginPassword");
        if (account) account.value = user;
        if (password) password.value = "123456";
        toast("已填入测试账号：" + user, "success");
      });
    });

    // 登录
    document.querySelectorAll("[data-login-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var account = form.querySelector('input[name="username"]') || form.querySelector('input[name="account"]');
        var password = form.querySelector('input[name="password"]');
        if (!account.value.trim() || !password.value) {
          toast("请输入账号和密码", "warning");
          return;
        }
        if (password.value.length < 6) {
          toast("密码至少 6 位", "error");
          return;
        }
        var api = window.FeiyiAPI;
        if (!api) {
          toast("接口层未加载，请刷新页面", "error");
          return;
        }
        if (api.config.mode === "live") {
          form.action = (api.config.baseURL || "") + "/auth/login";
          form.method = "post";
          form.submit();
          return;
        }
        api.auth.login(account.value.trim(), password.value).then(function (res) {
          toast("登录成功，正在进入平台…", "success");
          window.setTimeout(function () {
            window.location.href = res.redirect || api.roleHome(res.user.role);
          }, 500);
        }).catch(function (err) {
          toast(err.message || "登录失败", "error");
        });
      });
    });

    // 注册
    document.querySelectorAll("[data-register-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var pwd = form.querySelector('input[name="password"]');
        var pwd2 = form.querySelector('input[name="password2"]');
        var agree = form.querySelector('input[type="checkbox"]');
        if (pwd.value.length < 8) {
          toast("密码至少 8 位，请包含字母与数字", "error");
          return;
        }
        if (pwd.value !== pwd2.value) {
          toast("两次输入的密码不一致", "error");
          return;
        }
        if (!agree.checked) {
          toast("请先阅读并同意用户协议与隐私说明", "warning");
          return;
        }
        var api = window.FeiyiAPI;
        if (!api) {
          toast("接口层未加载，请刷新页面", "error");
          return;
        }
        if (api.config.mode === "live") {
          form.action = (api.config.baseURL || "") + "/auth/register";
          form.method = "post";
          form.submit();
          return;
        }
        var roleInput = form.querySelector('input[name="role"]:checked');
        api.auth.register({
          username: (form.querySelector('input[name="username"]') || {}).value || "",
          real_name: (form.querySelector('input[name="real_name"]') || {}).value || "",
          email: (form.querySelector('input[name="email"]') || {}).value || "",
          password: pwd.value,
          role: roleInput ? roleInput.value : "user"
        }).then(function () {
          toast("注册成功，请登录", "success");
          window.setTimeout(function () {
            window.location.href = "login.html";
          }, 700);
        }).catch(function (err) {
          toast(err.message || "注册失败", "error");
        });
      });
    });

    // 上传
    document.querySelectorAll("[data-upload]").forEach(function (label) {
      var input = label.querySelector('input[type="file"]');
      if (!input) return;
      input.addEventListener("change", function () {
        if (input.files && input.files.length) {
          toast("已选择文件：" + input.files[0].name, "success");
        }
      });
    });

    // 审核工作台
    bindReviewList();

    // AI 问答
    bindChat();

    // 通知中心
    initNotifications();

    // 顶栏搜索关键词过滤
    initQueryFilter();

    // 帮助中心搜索
    initHelpSearch();

    // 接口动作
    bindApiActions();

    // 顶栏账号与未读通知
    hydrateSession();

    // 表格筛选
    document.querySelectorAll("[data-filter-submit]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        toast("筛选条件已应用", "success");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.FeiyiUI = { toast: toast, icon: icon };
})();