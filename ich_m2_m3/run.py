# [负责人：周世航 | 启动入口 | Waitress 生产级 WSGI，默认 http://127.0.0.1:8000]
"""启动入口（run.py）

编写依据
--------
- 《系统接口清单》V2.0 §1：Base URL = http://127.0.0.1:8000（前端 Vite 把
  /api 与 /media 代理到这个地址，同源、无 CORS）；
- 报告 5.5 安全与部署：演示/验收用 Waitress（Windows 友好的生产级 WSGI
  服务器），不用 `flask run` / app.run(debug=True) 对外服务。

用法
----
    python seed.py          # 首次：建表 + 种子数据（含演示账号，密码 123456）
    python run.py           # Waitress 正式服务，http://127.0.0.1:8000
    python run.py --dev     # Flask 开发服务器（debug 热重载，仅本地开发用）

环境变量
--------
可写在同目录 .env（模板见 .env.example；.env 已被 .gitignore 忽略，勿提交真实密钥）。
优先级：真实环境变量 > .env > 代码默认值（load_dotenv 默认不覆盖已存在的变量）。
    HOST / PORT             监听地址，默认 127.0.0.1:8000
    SECRET_KEY              会话/CSRF 签名密钥，演示/部署前必须注入
    DATABASE_URL            缺省 sqlite:///instance/app.db；可一键切 MySQL
    DASHSCOPE_API_KEY       千问（M5 AI 问答）
    SILICONFLOW_API_KEY     bge-m3 向量化（M5 索引重建）
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- 加载 .env（python-dotenv）---
# 只补缺失的环境变量，不覆盖真实环境变量；未安装 dotenv 时也允许纯环境变量启动。
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass

from app import create_app  # noqa: E402  （必须在 load_dotenv 之后导入/调用）


def main():
    parser = argparse.ArgumentParser(description="非遗数字化管理平台启动入口")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Flask 开发服务器（debug=True，仅本地开发，禁止用于演示/验收）",
    )
    args = parser.parse_args()

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))  # 接口约定 V2.0：默认 8000

    app = create_app()

    # --- 启动自检提示（不阻塞启动，只把配置问题显性化）---
    if app.config["SECRET_KEY"] == "dev-only-insecure-key":
        print("[警告] 未设置 SECRET_KEY，正在使用开发兜底值；演示/部署前必须注入（见 .env.example）")
    if not app.config.get("DASHSCOPE_API_KEY"):
        print("[提示] 未设置 DASHSCOPE_API_KEY：AI 问答不可用/降级（M5），其余功能不受影响")
    if not app.config.get("SILICONFLOW_API_KEY"):
        print("[提示] 未设置 SILICONFLOW_API_KEY：向量化不可用，索引重建会失败（M5）")

    url = f"http://{host}:{port}"
    if args.dev:
        print(f"[开发模式] Flask dev server {url}（debug=True，勿用于演示/验收）")
        app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve

        print(f"[Waitress] 服务已启动 {url}（threads=8，Ctrl+C 停止）")
        print("[联调] 前端 Vite 代理目标即本地址；SPA 写请求前先 GET /api/csrf 取 token")
        serve(app, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()
