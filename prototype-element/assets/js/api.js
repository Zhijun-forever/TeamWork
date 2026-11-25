/* =========================================================
   非遗数字化管理平台 · 前端接口层
   依据《系统接口清单 V1.1》《数据库表设计 V1.1》
   - 后端未就绪时默认 mock 模式，返回与接口一致的数据结构
   - 设置 window.FEIYI_CONFIG = { mode: "live", baseURL: "http://127.0.0.1:8000" } 可切换真实请求
   ========================================================= */
(function () {
  "use strict";

  var runtime = window.FEIYI_CONFIG || {};
  var config = {
    baseURL: typeof runtime.baseURL === "string" ? runtime.baseURL.replace(/\/$/, "") : "",
    mode: runtime.mode === "live" ? "live" : "mock",
    mockDelay: typeof runtime.mockDelay === "number" ? runtime.mockDelay : 260,
    timeout: typeof runtime.timeout === "number" ? runtime.timeout : 15000
  };

  /* ---------- 枚举与展示文案（与数据库 CHECK 值一致） ---------- */
  var MAPS = {
    role: { sysadmin: "系统管理员", admin: "管理员", manager: "项目管理者", user: "普通用户" },
    status: { draft: "草稿", pending: "待审核", published: "已发布", rejected: "已驳回", archived: "已归档" },
    visibility: { public: "公开", internal: "不公开" },
    level: { national: "国家级", provincial: "省级", city: "市级", county: "县级" },
    certStatus: { pending: "待审批", approved: "已通过", rejected: "已驳回", revoked: "已撤销" },
    editStatus: { pending: "待审批", approved: "已同意", rejected: "已拒绝" },
    userStatus: { active: "启用", disabled: "已禁用", deleted: "已注销" },
    aiMode: { rag: "RAG 生成", retrieval: "检索降级", keyword: "关键词检索" },
    notifyType: { review: "审核", certification: "认证", system: "系统", project: "项目" }
  };

  function roleHome(role) {
    if (role === "manager") return "../admin/projects.html";
    if (role === "admin" || role === "sysadmin") return "../admin/dashboard.html";
    return "../site/home.html";
  }

  /* ---------- 错误对象 ---------- */
  function ApiError(message, status, code, data) {
    this.name = "ApiError";
    this.message = message || "请求失败";
    this.status = status || 0;
    this.code = code || "ERROR";
    this.data = data || null;
  }
  ApiError.prototype = Object.create(Error.prototype);

  /* ---------- Mock 数据 ---------- */
  var now = "2026-11-25 10:24";
  var mock = {
    session: null,
    notifications: [
      {
        id: 1, type: "review", title: "有 3 个项目等待审核",
        content: "景德镇手工制瓷技艺、潍坊风筝、侗戏已提交审核，最早一条已等待 26 小时。",
        created_at: "2026-11-25 10:18", read: false, link: "review.html"
      },
      {
        id: 2, type: "certification", title: "新的项目认证申请",
        content: "王秀兰申请认证「苗族刺绣」，材料包含单位证明与项目授权函。",
        created_at: "2026-11-25 09:42", read: false, link: "certifications.html"
      },
      {
        id: 3, type: "project", title: "项目审核已通过",
        content: "「苗族刺绣」已通过审核并发布，知识库将在下一次重建时纳入索引。",
        created_at: "2026-11-24 16:30", read: false, link: "projects.html"
      },
      {
        id: 4, type: "system", title: "数据库备份完成",
        content: "app-20261125-0300.db 已生成，包含数据库与上传目录，备份保留 7 天。",
        created_at: "2026-11-25 03:00", read: true, link: "ops.html"
      },
      {
        id: 5, type: "review", title: "归档修改申请待处理",
        content: "manager05 申请恢复「藏医药浴法」编辑权限，理由为补充年度传承活动记录。",
        created_at: "2026-11-24 16:20", read: true, link: "archive.html"
      },
      {
        id: 6, type: "system", title: "知识库索引异常已恢复",
        content: "「泉州提线木偶戏」索引失败，系统已重新排队，当前队列 2 个任务。",
        created_at: "2026-11-23 11:40", read: true, link: "ai.html"
      }
    ],
    users: [
      { id: 1, username: "admin01", real_name: "陈立", role: "admin", status: "active", phone: "13800000021", email: "admin01@example.org", created_at: "2026-09-01 09:20" },
      { id: 2, username: "manager01", real_name: "赵敏", role: "manager", status: "active", phone: "13900003382", email: "zhaomin@example.org", created_at: "2026-09-12 10:05" },
      { id: 3, username: "manager02", real_name: "钱进", role: "manager", status: "active", phone: "13700006615", email: "qianjin@example.org", created_at: "2026-09-18 14:40" },
      { id: 4, username: "user01", real_name: "林晓", role: "user", status: "active", phone: "13600008842", email: "linxiao@example.org", created_at: "2026-10-02 19:10" },
      { id: 5, username: "user02", real_name: "张弛", role: "user", status: "disabled", phone: "13400007756", email: "zhangchi@example.org", created_at: "2026-09-28 11:30" },
      { id: 6, username: "manager07", real_name: "王秀兰", role: "manager", status: "active", phone: "13500002290", email: "wangxl@example.org", created_at: "2026-11-20 16:20" },
      { id: 7, username: "admin02", real_name: "陈雨桐", role: "admin", status: "active", phone: "13300001908", email: "admin02@example.org", created_at: "2026-10-08 08:40" }
,
      { id: 8, username: "sysadmin", real_name: "系统管理员", role: "sysadmin", status: "active", phone: "", email: "sysadmin@example.org", created_at: "2026-08-20 09:00" }
    ],
    projects: [
      { id: 12, title: "苗族刺绣", summary: "以破线绣、绉绣、堆绣见长，纹样多取蝴蝶妈妈、龙、鸟等意象。", region_name: "贵州省 / 黔东南州", category_name: "传统美术", level: "国家级", status: "published", visibility: "public", views: 12480, owner_name: "manager01", created_at: "2026-11-18 16:40", updated_at: "2026-11-21 10:24", archived_at: null },
      { id: 11, title: "侗族大歌", summary: "多声部、无指挥、无伴奏的民间合唱，2009 年列入人类非遗代表作名录。", region_name: "贵州省 / 黔东南州", category_name: "传统音乐", level: "国家级", status: "published", visibility: "public", views: 9860, owner_name: "manager01", created_at: "2026-11-17 09:20", updated_at: "2026-11-20 15:12", archived_at: null },
      { id: 10, title: "景德镇手工制瓷技艺", summary: "拉坯、利坯、施釉、烧窑等七十余道工序，以“白如玉、薄如纸、声如磬”著称。", region_name: "江西省 / 景德镇市", category_name: "传统技艺", level: "国家级", status: "pending", visibility: "public", views: 8310, owner_name: "manager02", created_at: "2026-11-18 17:22", updated_at: "2026-11-19 09:40", archived_at: null },
      { id: 9, title: "南京云锦织造技艺", summary: "大花楼木织机双人配合，逐花异色，素有“寸锦寸金”之说。", region_name: "江苏省 / 南京市", category_name: "传统技艺", level: "国家级", status: "published", visibility: "public", views: 7940, owner_name: "manager03", created_at: "2026-11-15 10:30", updated_at: "2026-11-18 16:05", archived_at: null },
      { id: 8, title: "泉州提线木偶戏", summary: "傀儡调与提线技艺结合，一尊木偶最多三十余条提线。", region_name: "福建省 / 泉州市", category_name: "传统戏剧", level: "国家级", status: "rejected", visibility: "public", views: 6720, owner_name: "manager04", created_at: "2026-11-15 16:42", updated_at: "2026-11-17 11:30", archived_at: null },
      { id: 7, title: "陕北剪纸", summary: "以剪纸纹样记录岁时节令与民间信仰，常用于窗花、喜花与祭祀。", region_name: "陕西省 / 延安市", category_name: "传统美术", level: "省级", status: "draft", visibility: "internal", views: 0, owner_name: "manager01", created_at: "2026-11-16 14:08", updated_at: "2026-11-16 14:08", archived_at: null },
      { id: 6, title: "藏医药浴法", summary: "以藏药煎煮液沐浴防治疾病，2018 年列入人类非遗代表作名录。", region_name: "西藏自治区 / 拉萨市", category_name: "传统医药", level: "国家级", status: "archived", visibility: "public", views: 5380, owner_name: "manager05", created_at: "2026-09-20 10:12", updated_at: "2026-10-12 15:30", archived_at: "2026-10-12 15:30" },
      { id: 5, title: "苏州评弹", summary: "评话与弹词合称，以“说、噱、弹、唱”见长。", region_name: "江苏省 / 苏州市", category_name: "曲艺", level: "省级", status: "published", visibility: "public", views: 4960, owner_name: "manager03", created_at: "2026-11-10 09:00", updated_at: "2026-11-14 10:18", archived_at: null },
      { id: 4, title: "昆曲", summary: "水磨腔婉转，曲词典雅，载歌载舞，《牡丹亭》《长生殿》流传至今。", region_name: "江苏省 / 苏州市", category_name: "传统戏剧", level: "国家级", status: "published", visibility: "public", views: 3900, owner_name: "manager03", created_at: "2026-11-08 10:12", updated_at: "2026-11-12 09:18", archived_at: null },
      { id: 3, title: "安塞腰鼓", summary: "融舞蹈、武术与打击乐于一体，是陕北年节的重要民俗场景。", region_name: "陕西省 / 延安市", category_name: "传统舞蹈", level: "省级", status: "published", visibility: "public", views: 4180, owner_name: "manager01", created_at: "2026-11-06 14:20", updated_at: "2026-11-11 14:02", archived_at: null },
      { id: 21, title: "苏州御窑金砖制作技艺", summary: "以阳澄湖泥为料，经选泥、练泥、制坯、烧制等工序，供宫殿铺墁。", region_name: "江苏省 / 苏州市", category_name: "传统技艺", level: "省级", status: "archived", visibility: "public", views: 2860, owner_name: "manager03", created_at: "2026-09-10 09:00", updated_at: "2026-09-30 10:12", archived_at: "2026-09-30 10:12" },
      { id: 26, title: "土家族织锦技艺", summary: "西兰卡普以丝线通经断纬，纹样取自山水、鸟兽与生活器物。", region_name: "贵州省 / 铜仁市", category_name: "传统技艺", level: "国家级", status: "archived", visibility: "public", views: 2410, owner_name: "manager06", created_at: "2026-08-28 09:00", updated_at: "2026-09-18 09:05", archived_at: "2026-09-18 09:05" }
    ],
    certifications: [
      { id: 18, user_name: "王秀兰", username: "manager07", unit: "黔东南州非遗中心", project_id: 12, project_title: "苗族刺绣", status: "pending", applied_at: "2026-11-24 15:20", comment: "" },
      { id: 19, user_name: "李承志", username: "manager08", unit: "龙泉青瓷博物馆", project_id: 18, project_title: "龙泉青瓷烧制技艺", status: "pending", applied_at: "2026-11-23 10:05", comment: "" },
      { id: 20, user_name: "陈雨桐", username: "manager09", unit: "苏州评弹团", project_id: 5, project_title: "苏州评弹", status: "pending", applied_at: "2026-11-24 09:32", comment: "" },
      { id: 15, user_name: "赵敏", username: "manager01", unit: "黔东南州非遗中心", project_id: 11, project_title: "侗族大歌", status: "approved", applied_at: "2026-10-30 11:00", comment: "材料完整" },
      { id: 12, user_name: "周文", username: "manager03", unit: "南京云锦研究所", project_id: 9, project_title: "南京云锦织造技艺", status: "approved", applied_at: "2026-10-26 09:00", comment: "" }
    ],
    editRequests: [
      { id: 7, project_id: 6, project_title: "藏医药浴法", requester_name: "manager05", reason: "补充 2026 年度传承活动记录与 2 张现场照片，需恢复编辑权限。", status: "pending", created_at: "2026-11-24 16:20" },
      { id: 6, project_id: 26, project_title: "土家族织锦技艺", requester_name: "manager06", reason: "更正保护单位名称，原填写为旧机构名。", status: "pending", created_at: "2026-11-23 09:48" }
    ],
    regions: [
      { id: 1, name: "贵州省", parent_id: null, level: "province", sort_order: 1 },
      { id: 2, name: "江苏省", parent_id: null, level: "province", sort_order: 2 },
      { id: 3, name: "浙江省", parent_id: null, level: "province", sort_order: 3 },
      { id: 4, name: "福建省", parent_id: null, level: "province", sort_order: 4 },
      { id: 5, name: "江西省", parent_id: null, level: "province", sort_order: 5 },
      { id: 6, name: "陕西省", parent_id: null, level: "province", sort_order: 6 },
      { id: 7, name: "河南省", parent_id: null, level: "province", sort_order: 7 },
      { id: 8, name: "安徽省", parent_id: null, level: "province", sort_order: 8 },
      { id: 9, name: "山东省", parent_id: null, level: "province", sort_order: 9 },
      { id: 10, name: "西藏自治区", parent_id: null, level: "province", sort_order: 10 },
      { id: 11, name: "黔东南州", parent_id: 1, level: "市级", sort_order: 1 },
      { id: 12, name: "黔南州", parent_id: 1, level: "市级", sort_order: 2 },
      { id: 13, name: "贵阳市", parent_id: 1, level: "市级", sort_order: 3 }
    ],
    categories: [
      { id: 1, name: "民间文学", code: "C01", sort_order: 1 },
      { id: 2, name: "传统音乐", code: "C02", sort_order: 2 },
      { id: 3, name: "传统舞蹈", code: "C03", sort_order: 3 },
      { id: 4, name: "传统戏剧", code: "C04", sort_order: 4 },
      { id: 5, name: "曲艺", code: "C05", sort_order: 5 },
      { id: 6, name: "传统体育、游艺与杂技", code: "C06", sort_order: 6 },
      { id: 7, name: "传统美术", code: "C07", sort_order: 7 },
      { id: 8, name: "传统技艺", code: "C08", sort_order: 8 },
      { id: 9, name: "传统医药", code: "C09", sort_order: 9 },
      { id: 10, name: "民俗", code: "C10", sort_order: 10 }
    ],
    tags: [
      { id: 1, name: "国家级" }, { id: 2, name: "省级" }, { id: 3, name: "手工技艺" },
      { id: 4, name: "少数民族" }, { id: 5, name: "节庆民俗" }, { id: 6, name: "口传文学" }
    ],
    reviewRecords: [
      { id: 1, project_id: 12, action: "approve", from_status: "pending", to_status: "published", reviewer_name: "admin01", comment: "资料完整，地区与门类归类正确。", created_at: "2026-11-21 10:24" },
      { id: 2, project_id: 8, action: "reject", from_status: "pending", to_status: "rejected", reviewer_name: "admin01", comment: "封面缺失，保护单位信息待补充。", created_at: "2026-11-17 11:30" }
    ],
    auditLogs: [
      { id: 1, created_at: "2026-11-25 10:24", username: "admin01", action: "approve_project", target_type: "project", target_id: 12, detail: "审核通过「苗族刺绣」", ip: "127.0.0.1" },
      { id: 2, created_at: "2026-11-25 10:02", username: "admin01", action: "login", target_type: "user", target_id: 1, detail: "账号密码登录", ip: "127.0.0.1" },
      { id: 3, created_at: "2026-11-25 09:40", username: "manager01", action: "submit_project", target_type: "project", target_id: 13, detail: "提交「潍坊风筝」审核", ip: "127.0.0.1" },
      { id: 4, created_at: "2026-11-25 03:00", username: "sysadmin", action: "backup", target_type: "system", target_id: null, detail: "生成数据库与上传目录备份", ip: "127.0.0.1" }
    ],
    chat: { remaining: 12, date: "2026-11-25" }
  };

  try {
    var savedSession = window.sessionStorage.getItem("feiyi.session");
    if (savedSession) mock.session = JSON.parse(savedSession);
  } catch (e) {}

  function saveSession(user) {
    mock.session = user ? clone(user) : null;
    try {
      if (mock.session) window.sessionStorage.setItem("feiyi.session", JSON.stringify(mock.session));
      else window.sessionStorage.removeItem("feiyi.session");
    } catch (e) {}
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function mockOk(data) {
    return new Promise(function (resolve) {
      setTimeout(function () { resolve(clone(data)); }, config.mockDelay);
    });
  }

  function mockFail(message, status, code) {
    return new Promise(function (_, reject) {
      setTimeout(function () { reject(new ApiError(message, status, code)); }, config.mockDelay);
    });
  }

  function findProject(id) {
    return mock.projects.find(function (p) { return p.id === Number(id); });
  }

  function findUserByName(username) {
    return mock.users.find(function (u) { return u.username === username; });
  }

  function touchProject(project) {
    project.updated_at = now;
  }

  /* ---------- Mock 路由 ---------- */
  function mockRequest(method, path, data) {
    var m;

    if (path === "/auth/login" && method === "POST") {
      var username = String(data.username || "").trim();
      var password = String(data.password || "");
      var user = findUserByName(username);
      if (!user) return mockFail("用户名或密码错误", 401, "INVALID_CREDENTIALS");
      if (user.status !== "active") return mockFail("账号已禁用，请联系管理员", 403, "ACCOUNT_DISABLED");
      if (password.length < 6) return mockFail("用户名或密码错误", 401, "INVALID_CREDENTIALS");
      saveSession(user);
      return mockOk({ user: clone(user), redirect: roleHome(user.role) });
    }

    if (path === "/auth/register" && method === "POST") {
      var name = String(data.username || "").trim();
      if (!name || !data.password) return mockFail("请填写用户名和密码", 400, "VALIDATION_ERROR");
      if (findUserByName(name)) return mockFail("用户名已存在", 409, "USERNAME_EXISTS");
      var role = data.role === "manager" ? "manager" : "user";
      var created = {
        id: mock.users.length + 10, username: name, real_name: data.real_name || name,
        role: role, status: "active", phone: data.phone || "", email: data.email || "",
        created_at: now
      };
      mock.users.push(created);
      return mockOk({ user: clone(created) });
    }

    if (path === "/auth/logout" && method === "POST") {
      saveSession(null);
      return mockOk({ redirect: "../site/login.html" });
    }

    if (path === "/me" && method === "GET") {
      return mock.session ? mockOk(clone(mock.session)) : mockFail("请先登录", 401, "UNAUTHORIZED");
    }

    if (path === "/me" && method === "POST") {
      if (!mock.session) return mockFail("请先登录", 401, "UNAUTHORIZED");
      if (data.action === "password") {
        if (!data.old_password || !data.new_password) return mockFail("请填写原密码与新密码", 400, "VALIDATION_ERROR");
        if (String(data.new_password).length < 8) return mockFail("新密码至少 8 位", 400, "VALIDATION_ERROR");
        return mockOk({ message: "密码已更新" });
      }
      if (data.action === "deactivate") return mockFail("当前角色不能注销账号", 403, "FORBIDDEN");
      Object.assign(mock.session, {
        real_name: data.real_name || mock.session.real_name,
        email: data.email || mock.session.email,
        phone: data.phone || mock.session.phone
      });
      var u = findUserByName(mock.session.username);
      if (u) Object.assign(u, mock.session);
      saveSession(mock.session);
      return mockOk({ user: clone(mock.session) });
    }

    if (path === "/projects" && method === "GET") {
      var items = mock.projects.filter(function (p) {
        if (data.scope === "mine") return p.owner_name === (mock.session && mock.session.username);
        if (data.scope === "all") return true;
        return p.status === "published" && p.visibility === "public";
      });
      if (data.q) {
        items = items.filter(function (p) {
          return (p.title + p.summary).indexOf(data.q) !== -1;
        });
      }
      if (data.status) items = items.filter(function (p) { return p.status === data.status; });
      if (data.category) items = items.filter(function (p) { return p.category_name === data.category; });
      var page = Number(data.page || 1);
      var per = 12;
      return mockOk({
        items: clone(items.slice((page - 1) * per, page * per)),
        total: items.length, page: page, per_page: per
      });
    }

    if ((m = path.match(/^\/projects\/(\d+)$/)) && method === "GET") {
      var p = findProject(m[1]);
      if (!p) return mockFail("项目不存在", 404, "NOT_FOUND");
      if (p.status !== "published" && !(mock.session && ["admin", "sysadmin"].indexOf(mock.session.role) !== -1)) {
        return mockFail("无权查看该项目", 403, "FORBIDDEN");
      }
      return mockOk({
        project: clone(p),
        detail: {
          content: "项目内容与技艺流程由保护单位整理，包含工序、纹样与代表作品等资料。",
          history: "项目历史渊源与传承谱系资料。",
          inheritance: "代表性传承人与传习活动记录。",
          protection: "记录性保护、生产性保护与展示传播措施。",
          source_url: "https://www.ihchina.cn/"
        },
        tags: clone(mock.tags.slice(0, 3)),
        media: [],
        review_records: clone(mock.reviewRecords.filter(function (r) { return r.project_id === p.id; }))
      });
    }

    if (path === "/projects/new" && method === "POST") {
      var np = {
        id: Math.max.apply(null, mock.projects.map(function (x) { return x.id; })) + 1,
        title: data.title || "未命名项目", summary: data.summary || "",
        region_name: data.region_name || "", category_name: data.category_name || "",
        level: data.level || "国家级", status: data.publish ? "published" : "draft",
        visibility: data.visibility || "public", views: 0,
        owner_name: mock.session ? mock.session.username : "manager01",
        created_at: now, updated_at: now, archived_at: null
      };
      mock.projects.unshift(np);
      return mockOk({ project: clone(np), redirect: "projects.html" });
    }

    if ((m = path.match(/^\/projects\/(\d+)\/edit$/)) && method === "POST") {
      var ep = findProject(m[1]);
      if (!ep) return mockFail("项目不存在", 404, "NOT_FOUND");
      Object.assign(ep, {
        title: data.title || ep.title, summary: data.summary || ep.summary,
        region_name: data.region_name || ep.region_name,
        category_name: data.category_name || ep.category_name,
        level: data.level || ep.level, visibility: data.visibility || ep.visibility
      });
      touchProject(ep);
      return mockOk({ project: clone(ep) });
    }

    if ((m = path.match(/^\/projects\/(\d+)\/status$/)) && method === "POST") {
      var sp = findProject(m[1]);
      if (!sp) return mockFail("项目不存在", 404, "NOT_FOUND");
      var action = data.action;
      var from = sp.status;
      if (action === "submit") {
        if (["draft", "rejected"].indexOf(sp.status) === -1) return mockFail("当前状态不能提交审核", 409, "STATUS_CONFLICT");
        sp.status = "pending";
      } else if (action === "approve") {
        if (sp.status !== "pending") return mockFail("当前状态不能审核", 409, "STATUS_CONFLICT");
        sp.status = "published"; sp.published_at = now;
      } else if (action === "reject") {
        if (sp.status !== "pending") return mockFail("当前状态不能驳回", 409, "STATUS_CONFLICT");
        if (!String(data.comment || "").trim()) return mockFail("驳回必须填写意见", 400, "VALIDATION_ERROR");
        sp.status = "rejected";
      } else if (action === "archive") {
        if (sp.status !== "published") return mockFail("只有已发布项目可以归档", 409, "STATUS_CONFLICT");
        sp.status = "archived"; sp.archived_at = now;
      } else if (action === "restore") {
        if (sp.status !== "archived") return mockFail("只有已归档项目可以恢复", 409, "STATUS_CONFLICT");
        sp.status = "published"; sp.archived_at = null;
      } else if (action === "request_edit") {
        if (sp.status !== "archived") return mockFail("只有已归档项目可以申请修改", 409, "STATUS_CONFLICT");
      } else if (action === "delete") {
        sp.status = "draft";
      } else {
        return mockFail("非法操作", 400, "INVALID_ACTION");
      }
      touchProject(sp);
      mock.reviewRecords.unshift({
        id: mock.reviewRecords.length + 1, project_id: sp.id, action: action,
        from_status: from, to_status: sp.status,
        reviewer_name: mock.session ? mock.session.username : "admin01",
        comment: data.comment || "", created_at: now
      });
      return mockOk({ project: clone(sp) });
    }

    if (path === "/admin/users" && method === "GET") {
      var users = mock.users.slice();
      if (data.q) users = users.filter(function (u) { return (u.username + u.real_name).indexOf(data.q) !== -1; });
      if (data.role) users = users.filter(function (u) { return u.role === data.role; });
      if (data.status) users = users.filter(function (u) { return u.status === data.status; });
      return mockOk({ items: clone(users), total: users.length, page: 1, per_page: 12 });
    }

    if (path === "/admin/users" && method === "POST") {
      return mockRequest("POST", "/auth/register", data);
    }

    if ((m = path.match(/^\/admin\/users\/(\d+)$/)) && method === "POST") {
      var target = mock.users.find(function (u) { return u.id === Number(m[1]); });
      if (!target) return mockFail("用户不存在", 404, "NOT_FOUND");
      Object.assign(target, {
        real_name: data.real_name || target.real_name,
        phone: data.phone || target.phone,
        email: data.email || target.email,
        status: data.status || target.status
      });
      return mockOk({ user: clone(target) });
    }

    if (path === "/admin/certifications" && method === "GET") {
      var certs = mock.certifications.slice();
      if (data.status) certs = certs.filter(function (c) { return c.status === data.status; });
      return mockOk({ items: clone(certs), total: certs.length, page: 1, per_page: 12 });
    }

    if ((m = path.match(/^\/admin\/certifications\/(\d+)$/)) && method === "POST") {
      var cert = mock.certifications.find(function (c) { return c.id === Number(m[1]); });
      if (!cert) return mockFail("认证申请不存在", 404, "NOT_FOUND");
      if (cert.status !== "pending") return mockFail("该申请已处理", 409, "STATUS_CONFLICT");
      if (data.action !== "approve" && data.action !== "reject") return mockFail("非法操作", 400, "INVALID_ACTION");
      cert.status = data.action === "approve" ? "approved" : "rejected";
      cert.comment = data.comment || "";
      return mockOk({ certification: clone(cert) });
    }

    if (path === "/manager/certifications" && method === "POST") {
      return mockOk({ message: data.action === "cancel" ? "认证申请已撤销" : "认证申请已提交" });
    }

    if (path === "/admin/taxonomy" && method === "GET") {
      return mockOk({ regions: clone(mock.regions), categories: clone(mock.categories), tags: clone(mock.tags) });
    }

    if (path === "/admin/taxonomy" && method === "POST") {
      var store = data.type === "category" ? mock.categories : data.type === "tag" ? mock.tags : mock.regions;
      if (data.action === "delete") return mockFail("该分类已被项目引用，不能删除", 409, "IN_USE");
      if (data.action === "create") {
        store.push({ id: store.length + 100, name: data.name, code: data.code || "", sort_order: 99 });
      }
      return mockOk({ message: "分类已保存" });
    }

    if (path === "/api/ai/chat" && method === "POST") {
      var question = String(data.question || "").trim();
      if (!question) return mockFail("请输入问题", 400, "VALIDATION_ERROR");
      if (mock.chat.remaining <= 0) return mockFail("今日提问次数已用完", 429, "RATE_LIMITED");
      var answer = {
        answer: "根据知识库，与“" + question + "”相关的公开项目可在项目库中按地区与门类检索。当前资料不足以给出更具体的结论，建议缩小地区或门类范围后再试。",
        mode: "keyword", sources: [], remaining: mock.chat.remaining
      };
      if (question.indexOf("苗族刺绣") !== -1 || question.indexOf("刺绣") !== -1) {
        answer = {
          answer: "根据知识库，与苗族刺绣相关的公开项目主要有：\n1. 苗族刺绣（贵州省 / 黔东南州，传统美术）——以破线绣、绉绣、堆绣见长。\n2. 水族马尾绣（贵州省 / 三都县，传统美术）——以马尾缠丝为芯，盘出立体纹样。\n以上信息来自平台公开项目资料。",
          mode: "rag",
          sources: [
            { project_id: 12, title: "苗族刺绣", category: "传统美术" },
            { project_id: 30, title: "水族马尾绣", category: "传统美术" }
          ],
          remaining: mock.chat.remaining
        };
      } else if (question.indexOf("音乐") !== -1 || question.indexOf("侗族大歌") !== -1) {
        answer = {
          answer: "贵州省收录的传统音乐类公开项目包括侗族大歌、苗族飞歌、布依族八音坐唱等。其中侗族大歌为多声部、无指挥、无伴奏的民间合唱，2009 年列入人类非遗代表作名录。",
          mode: "rag",
          sources: [{ project_id: 11, title: "侗族大歌", category: "传统音乐" }],
          remaining: mock.chat.remaining
        };
      } else if (question.indexOf("比较") !== -1) {
        answer = {
          answer: "苗族刺绣属于传统美术，核心在纹样与针法；侗族大歌属于传统音乐，核心在多声部合唱与口传心授。两者都依托黔东南地区社区传承，但前者以物质载体呈现，后者以声音与仪式场景呈现。",
          mode: "rag",
          sources: [
            { project_id: 12, title: "苗族刺绣", category: "传统美术" },
            { project_id: 11, title: "侗族大歌", category: "传统音乐" }
          ],
          remaining: mock.chat.remaining
        };
      } else if (question.indexOf("戏剧") !== -1 || question.indexOf("推荐") !== -1) {
        answer = {
          answer: "推荐 3 个传统戏剧类公开项目：昆曲（江苏 / 苏州）、泉州提线木偶戏（福建 / 泉州）、侗戏（贵州 / 黎平）。",
          mode: "rag",
          sources: [
            { project_id: 4, title: "昆曲", category: "传统戏剧" },
            { project_id: 8, title: "泉州提线木偶戏", category: "传统戏剧" },
            { project_id: 14, title: "侗戏", category: "传统戏剧" }
          ],
          remaining: mock.chat.remaining
        };
      } else if (question.indexOf("天气") !== -1) {
        answer = {
          answer: "该问题超出平台知识库范围。我只能回答与非遗项目相关的问题。",
          mode: "reject", sources: [], remaining: mock.chat.remaining
        };
      }
      mock.chat.remaining -= 1;
      answer.remaining = mock.chat.remaining;
      return mockOk(answer);
    }

    if (path === "/admin/ai/rebuild" && method === "POST") {
      return mockOk({ projects: 38, chunks: 386 });
    }

    if (path === "/admin/ops" && method === "GET") {
      return mockOk({
        stats: { uptime: "12 天 6 小时", db_size: "6.4 MB", requests_today: 386, error_rate: "0.2%" },
        info: {
          framework: "Flask 3.x · Jinja2", python: "3.12", database: "SQLite 3 · WAL",
          deploy: "Waitress · 127.0.0.1:8000", embedding: "bge-m3 · 1024 维",
          model: "qwen-turbo · max_tokens 400", tables: 14, backup: "每日 03:00 · 保留 7 份"
        },
        logs: clone(mock.auditLogs)
      });
    }

    if (path === "/admin/backup" && method === "GET") {
      return mockOk({ filename: "app-20261125-1032.zip", size: "54.4 MB", message: "备份文件已生成" });
    }

    if (path === "/healthz" && method === "GET") {
      return mockOk({ status: "ok", db: "ok", ai: "ok" });
    }

    if (path === "/api/notifications" && method === "GET") {
      var notes = mock.notifications.slice();
      if (data.status === "unread") notes = notes.filter(function (n) { return !n.read; });
      else if (data.status === "read") notes = notes.filter(function (n) { return n.read; });
      if (data.type) notes = notes.filter(function (n) { return n.type === data.type; });
      if (data.q) notes = notes.filter(function (n) { return (n.title + n.content).indexOf(data.q) !== -1; });
      return mockOk({
        items: clone(notes), total: notes.length,
        unread: mock.notifications.filter(function (n) { return !n.read; }).length
      });
    }

    if ((m = path.match(/^\/api\/notifications\/(\d+)\/read$/)) && method === "POST") {
      var note = mock.notifications.find(function (n) { return n.id === Number(m[1]); });
      if (!note) return mockFail("通知不存在", 404, "NOT_FOUND");
      note.read = true;
      return mockOk({ notification: clone(note) });
    }

    if (path === "/api/notifications/read-all" && method === "POST") {
      mock.notifications.forEach(function (n) { n.read = true; });
      return mockOk({ unread: 0 });
    }

    return mockFail("接口暂未实现：" + method + " " + path, 404, "NOT_IMPLEMENTED");
  }

  /* ---------- 真实请求 ---------- */
  function readCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute("content")) return meta.getAttribute("content");
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function buildQuery(query) {
    if (!query) return "";
    var parts = [];
    Object.keys(query).forEach(function (key) {
      var value = query[key];
      if (value === undefined || value === null || value === "") return;
      if (Array.isArray(value)) {
        value.forEach(function (item) { parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(item)); });
      } else {
        parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(value));
      }
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  function request(method, path, options) {
    options = options || {};
    if (config.mode === "mock") return mockRequest(method, path, options.form || options.data || {});
    var query = buildQuery(options.query);
    var url = config.baseURL + path + query;
    var headers = Object.assign({ Accept: "application/json" }, options.headers || {});
    var body = null;
    var csrf = readCsrfToken();
    if (csrf && method !== "GET") headers["X-CSRFToken"] = csrf;

    if (options.form) {
      body = new FormData();
      Object.keys(options.form).forEach(function (key) {
        var value = options.form[key];
        if (value === undefined || value === null) return;
        if (Array.isArray(value)) value.forEach(function (v) { body.append(key, v); });
        else body.append(key, value);
      });
    } else if (options.data !== undefined && method !== "GET") {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.data);
    }

    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, config.timeout) : null;

    return fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: headers,
      body: body,
      signal: controller ? controller.signal : undefined
    }).then(function (res) {
      if (timer) clearTimeout(timer);
      var type = res.headers.get("content-type") || "";
      if (type.indexOf("application/json") !== -1) {
        return res.json().then(function (payload) {
          if (!res.ok) {
            throw new ApiError(payload.message || "请求失败", res.status, payload.code, payload.data);
          }
          if (payload && payload.code && payload.code !== "OK") {
            throw new ApiError(payload.message || "请求失败", res.status, payload.code, payload.data);
          }
          return payload && Object.prototype.hasOwnProperty.call(payload, "data") ? payload.data : payload;
        });
      }
      if (!res.ok) throw new ApiError("请求失败（" + res.status + "）", res.status, "HTTP_" + res.status);
      return res.text();
    }).catch(function (err) {
      if (timer) clearTimeout(timer);
      if (err && err.name === "AbortError") throw new ApiError("请求超时，请稍后重试", 0, "TIMEOUT");
      if (err instanceof ApiError) throw err;
      throw new ApiError("网络异常，请检查服务是否可用", 0, "NETWORK_ERROR");
    });
  }

  function get(path, query) { return request("GET", path, { query: query }); }
  function post(path, data, form) { return request("POST", path, { data: form ? undefined : data, form: form ? data : null }); }

  /* ---------- 业务接口 ---------- */
  var api = {
    config: config,
    maps: MAPS,
    roleHome: roleHome,
    setMode: function (mode, baseURL) {
      config.mode = mode === "live" ? "live" : "mock";
      if (typeof baseURL === "string") config.baseURL = baseURL.replace(/\/$/, "");
    },
    getMode: function () { return config.mode; },

    auth: {
      login: function (username, password) { return post("/auth/login", { username: username, password: password }, true); },
      register: function (payload) { return post("/auth/register", payload, true); },
      logout: function () { return post("/auth/logout", {}); }
    },

    me: {
      get: function () { return get("/me"); },
      updateProfile: function (payload) { return post("/me", Object.assign({ action: "profile" }, payload), true); },
      updatePassword: function (payload) { return post("/me", Object.assign({ action: "password" }, payload), true); },
      deactivate: function () { return post("/me", { action: "deactivate" }); }
    },

    users: {
      list: function (query) { return get("/admin/users", query); },
      create: function (payload) { return post("/admin/users", payload, true); },
      update: function (id, payload) { return post("/admin/users/" + id, payload, true); }
    },

    certifications: {
      mine: function (query) { return get("/manager/certifications", query); },
      list: function (query) { return get("/admin/certifications", query); },
      apply: function (payload) { return post("/manager/certifications", Object.assign({ action: "apply" }, payload), true); },
      review: function (id, action, comment) { return post("/admin/certifications/" + id, { action: action, comment: comment || "" }, true); }
    },

    projects: {
      list: function (query) { return get("/projects", query); },
      get: function (id) { return get("/projects/" + id); },
      create: function (payload) { return post("/projects/new", payload, true); },
      update: function (id, payload) { return post("/projects/" + id + "/edit", payload, true); },
      status: function (id, action, comment) { return post("/projects/" + id + "/status", { action: action, comment: comment || "" }, true); }
    },

    taxonomy: {
      get: function () { return get("/admin/taxonomy"); },
      save: function (payload) { return post("/admin/taxonomy", payload, true); }
    },

    ai: {
      chat: function (question) { return post("/api/ai/chat", { question: question }); },
      rebuild: function () { return post("/admin/ai/rebuild", {}); }
    },

    ops: {
      get: function (tab, page) { return get("/admin/ops", { tab: tab || "stats", page: page || 1 }); },
      backup: function () { return get("/admin/backup"); }
    },

    notifications: {
      list: function (query) { return get("/api/notifications", query); },
      markRead: function (id) { return post("/api/notifications/" + id + "/read", {}); },
      markAllRead: function () { return post("/api/notifications/read-all", {}); },
      unreadCount: function () {
        return get("/api/notifications", { status: "unread" }).then(function (res) {
          return typeof res.unread === "number" ? res.unread : (res.items || []).length;
        });
      }
    },

    health: function () { return get("/healthz"); }
  };

  window.FeiyiAPI = api;
})();