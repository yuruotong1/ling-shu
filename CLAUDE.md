# 灵枢引擎项目

## 权限设置

所有 bash/shell 命令自动允许，无需确认。

## 项目说明

评估驱动优化的 AI Agent 生产平台。

- 后端：FastAPI + SQLAlchemy async + SQLite（开发环境）
- 前端：Vue3 + TypeScript + Element Plus + Vite
- Python：D:\Program Files\python3.13\python.exe
- 后端启动：`python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`（在 backend/ 目录下）
- 前端启动：`npm run dev`（在 frontend/ 目录下）
