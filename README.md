# Guess — 赛马竞猜投票平台

面向赛马爱好者圈子的竞猜投票网站。每场比赛每个用户只选一匹自己认为会赢的马，比赛结束后系统根据等级规则自动结算积分。

## 技术栈

- **前端**: Vue 3 + Vite + TypeScript + Vue Router 4 + Pinia + Axios
- **后端**: FastAPI + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL 16
- **部署**: Docker Compose（VPS）

## 本地开发

### 前置条件

- Node.js 20+
- pnpm 9+
- Python 3.12+
- Docker & Docker Compose

### 启动步骤

```bash
# 1. 启动 PostgreSQL
docker compose up -d

# 2. 启动后端
cd backend
cp ../.env.example .env
# 创建并激活虚拟环境: python -m venv venv
# 安装依赖: pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. 启动前端（新终端）
cd frontend
pnpm install
pnpm dev
```

### 访问

- 前端: http://localhost:5173
- API 文档: http://localhost:8000/docs
- 数据库: localhost:5432 (guess / guess_password)

### 导入历史得分

更新后端依赖后，在 `backend` 目录执行 `alembic upgrade head`，然后以管理员登录，在排行榜页面选择“导入历史得分”。工作簿需要包含“历史得分”和“赛事资料”工作表；历史得分表每行一个用户、每列一场比赛，导入前请为每行填写 QQ 号。

历史比赛独立于首页比赛保存，并按 QQ 与用户关联。非空得分（包括 0）计入总分和场次；赛事资料用于排行榜筛选，参赛马匹数为空时按 0 处理。与现有比赛或已导入历史比赛的名称和日期相同的比赛会被跳过，不覆盖已有成绩。

## 项目结构

```
guess/
├── frontend/          # Vue 3 + Vite 前端
├── backend/           # FastAPI 后端
├── docker-compose.yml # PostgreSQL 16
└── .env.example       # 环境变量模板
```
