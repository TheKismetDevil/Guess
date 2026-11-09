# 项目约定

## Git 分支与 PR 流程

开发新功能、修复或重构时，不直接在 `master` 上提交，使用短生命周期分支并通过 PR 合并（GitHub Flow）。

- 开工前先 `git status -sb` 检查当前分支和未提交改动；若仍在 `master`，先同步 `git pull origin master`，再新建分支。
- 分支命名：`feat/<简述>`、`fix/<简述>`、`refactor/<简述>`、`docs/<简述>`、`test/<简述>`，使用小写英文和连字符，如 `feat/qq-avatar`。
- 一个分支只做一件事；提交信息沿用 Conventional Commits（`feat:`、`fix:`、`test:`、`docs:`…），小步提交。
- 提交前在本地跑通相关测试（见 `docs/testing.md`）；PR 会触发 `.github/workflows/tests.yml`，CI 全绿后再合并，默认使用 Squash and merge 并删除远端分支。
- 远端：`origin` 为主仓库 `TheKismetDevil/Guess`，`alzawok` 为协作者 fork。推送使用 `git push -u origin <分支名>`，PR 目标分支为 `origin/master`。
- 本机未安装 GitHub CLI（`gh`），推送后告知用户在 GitHub 页面创建 PR，并附上 PR 标题和描述草稿。
- 未经用户确认，不要 force push、改写 `master` 历史或删除他人分支。
- 在受限沙箱中，git 写操作（新建分支、commit、push）会因无法写入 `.git` 失败，后端异步 pytest 用例也可能挂起；遇到时改为在沙箱外执行该条命令。
- 新功能涉及的新约定须同步更新 `_bmad-output/project-context.md`，与代码一起提交到同一 PR。

## 开启本地测试

用户说“开启测试”“启动测试”或类似请求时，先读取并按照 `.vscode/local-testing.md` 的最新指令启动本地测试环境。

- 启动前检查现有服务和端口，避免重复启动。
- 按文档启动 Docker Compose、后端 Uvicorn 和前端 Vite，并保持服务运行。
- 启动后验证服务可访问，并告知用户访问地址；若失败，检查日志并说明原因。

## 清空比赛数据

- 先确认用户要求清空的范围，检查 `races`、`historical_races` 和关联表的记录数；保留用户和马匹等未明确要求删除的数据。
- 本地 PostgreSQL 容器为 `guess-postgres`，数据库和用户均为 `guess`。删除前使用 `pg_dump` 备份相关表到 `outputs/database-backups/`，确认备份成功。
- 清空历史比赛可在事务中执行 `DELETE FROM historical_races;`；数据库外键会级联删除 `historical_scores`。执行后检查两个表的记录数，并告知用户备份位置。其他比赛数据须先检查外键及影响，再按确认的范围处理。
