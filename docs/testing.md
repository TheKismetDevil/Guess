# 自动化测试

## 安装依赖

前端使用 Node.js 24、pnpm 11.5.2；后端使用 Python 3.12。先在项目根目录创建并安装独立 Python 环境：

```powershell
python -m venv backend/venv
backend/venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
pnpm install --frozen-lockfile
```

## Windows 一键运行

回到项目根目录：

```powershell
./scripts/test.ps1 -PythonExe ./backend/venv/Scripts/python.exe
```

脚本依次执行前端测试类型检查、Node 回归测试、Vitest DOM 组件测试、生产构建以及 SQLite 后端测试。任一步失败即停止并返回失败。

需要验证真实 PostgreSQL 时，先打开 Docker Desktop，再运行：

```powershell
./scripts/test.ps1 -PythonExe ./backend/venv/Scripts/python.exe -IncludePostgres
```

脚本只管理 Compose 项目 `guess-tests` 的测试容器，使用 `127.0.0.1:55432` 和 `guess_test` 数据库。由脚本启动的测试容器会在结束或失败后清理；已有的运行中测试容器会保留。实际应用的 `guess-postgres` 和数据库 `guess` 不会被使用。

## 分别运行

在 `frontend`：

```text
pnpm test                # Node 回归 + Vitest DOM 组件测试
pnpm run test:unit       # 仅 DOM 组件测试
pnpm run test:watch      # Vitest 监听模式
pnpm run test:typecheck  # 检查应用与测试代码的类型
pnpm build              # 应用类型检查与生产构建
```

在 `backend`，使用已安装依赖的 Python：

```text
python -m pytest -m "not postgres" -q
```

PostgreSQL 集成测试可单独运行，在项目根目录启动独立服务：

```powershell
docker compose -p guess-tests -f compose.test.yml up -d --wait
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://guess_test:guess_test_password@localhost:55432/guess_test'
cd backend
python -m pytest -m postgres -q
```

每个 PostgreSQL 用例使用一个随机 `test_guess_*` schema，并在结束后删除自己的 schema。连接地址必须显式配置，且数据库名必须以 `_test` 结尾。未设置 `TEST_DATABASE_URL` 时，用例跳过；配置不符合条件时直接失败。不会回退到应用数据库，也不会清空数据库级别的数据。

## 当前覆盖

- 原有 Node 回归测试：认证续期、投票回滚、排序菜单、Head to Head 异步请求。
- Vitest + Vue Test Utils + happy-dom：排序菜单真实 DOM 点击/键盘/焦点/外部关闭，排行榜排序/60%说明/筛选/过期请求，历史导入默认选项/重新预览/差异确认/文件大小/冲突/撤销确认，Head to Head 选择/逐场分数/合计/筛选/搜索/重试。
- SQLite pytest：原有认证、比赛、投票、结算、排行榜、历史导入等接口与业务规则。
- PostgreSQL：从空库执行全部迁移，旧成绩批次回填，历史导入差异更新与撤销，投票锁定、结算重算、真实距离筛选与三位小数 SQL 聚合。

这些 DOM 测试不等同于真实浏览器的布局或截图测试。

## GitHub Actions

`.github/workflows/tests.yml` 在 push、pull request 和手动触发时运行。前端执行锁文件安装、测试类型检查、两套测试和构建；后端使用 Python 3.12，分别执行 SQLite 与临时 PostgreSQL 测试。工作流只需要仓库读取权限，不使用生产凭据。推送这份配置后才会在远端触发。
