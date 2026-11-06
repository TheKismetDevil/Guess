# 项目约定

## 开启本地测试

用户说“开启测试”“启动测试”或类似请求时，先读取并按照 `.vscode/local-testing.md` 的最新指令启动本地测试环境。

- 启动前检查现有服务和端口，避免重复启动。
- 按文档启动 Docker Compose、后端 Uvicorn 和前端 Vite，并保持服务运行。
- 启动后验证服务可访问，并告知用户访问地址；若失败，检查日志并说明原因。

## 清空比赛数据

- 先确认用户要求清空的范围，检查 `races`、`historical_races` 和关联表的记录数；保留用户和马匹等未明确要求删除的数据。
- 本地 PostgreSQL 容器为 `guess-postgres`，数据库和用户均为 `guess`。删除前使用 `pg_dump` 备份相关表到 `outputs/database-backups/`，确认备份成功。
- 清空历史比赛可在事务中执行 `DELETE FROM historical_races;`；数据库外键会级联删除 `historical_scores`。执行后检查两个表的记录数，并告知用户备份位置。其他比赛数据须先检查外键及影响，再按确认的范围处理。
