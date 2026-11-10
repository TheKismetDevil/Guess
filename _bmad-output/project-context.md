---
project_name: 'guess'
user_name: 'tkd'
date: '2026-07-10'
story: 'lock-confirm-and-edit-gate-label'
sections_completed:
  ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow', 'critical_rules']
status: 'complete'
rule_count: 98
optimized_for_llm: true
---


# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend Framework | Vue 3 | ^3.5.34 | Composition API + `<script setup>` |
| Build Tool | Vite | ^8.0.16 | HMR, vue plugin |
| Language | TypeScript | ~6.0.2 | Strict mode |
| State Management | Pinia | ^2.3.1 | `use{Name}Store` pattern |
| Router | Vue Router 4 | ^4.6.4 | Lazy loaded routes |
| HTTP Client | Axios | ^1.17.0 | Interceptors for auth/refresh |
| CSS | CSS Variables + scoped CSS | — | JRA design system, no UI library |
| Package Manager | pnpm | ^9+ | Frontend only; workspace uses `nodeLinker: hoisted` |
| Backend Framework | FastAPI | >=0.110 | Async native |
| ORM | SQLAlchemy 2.0 | >=2.0 | Async mode with asyncpg |
| Migration | Alembic | >=1.13 | Async template (`-t async`) |
| Database | PostgreSQL 16 | Docker image `postgres:16-alpine` | Local dev via Docker Compose |
| Auth | JWT (python-jose) | >=3.3 | access_token 30min + refresh 7d; `ExpiredSignatureError` vs `JWTError` handled separately |
| Password Hashing | passlib[bcrypt] | >=1.7 | CryptContext |
| Async Driver | asyncpg | >=0.29 | — |
| Python | Python | >=3.12 | — |
| Testing (Backend) | pytest + pytest-asyncio + aiosqlite | >=8 / >=0.23 / >=0.19 | `asyncio_mode = auto`; in-memory SQLite for isolated tests |
| Testing (Frontend) | Node test + Vitest / Vue Test Utils / happy-dom | — | `pnpm test` runs both suites; DOM tests in `tests/unit/` |
| Container | Docker Compose | — | PostgreSQL only; frontend/backend run locally |

## Critical Implementation Rules

### Language-Specific Rules

**TypeScript/Vue:**
- Component files: **PascalCase** (`RaceCard.vue`), non-component: **camelCase** (`useAuth.ts`, `apiClient.ts`)
- Pinia stores: `use{Name}Store` pattern (`useRaceStore`, `useAuthStore`)
- Page components must be **lazy loaded** via dynamic `import()` in router
- Vue Router: `createWebHistory()` — no hash mode
- TypeScript types in `src/types/`, organized by domain (auth.ts, race.ts, horse.ts, vote.ts, leaderboard.ts)
- CSS variables: **kebab-case** (`--color-primary`, `--spacing-4`)
- API字段在前后端之间使用 **snake_case**（不转换 camelCase）
- **PageState 枚举模式**：列表页面使用 `type PageState = 'loading' | 'empty' | 'error' | 'success'`，搜索/下拉组件可使用扩展版 `'idle' | 'loading' | 'empty' | 'error' | 'success'`（`idle` 表示初始未搜索状态，下拉隐藏）。骨架屏显示 loading 态，精确微文案显示 empty 态，"加载失败，请刷新重试"+刷新按钮显示 error 态。
- `RaceCard.vue` 支持 `skeleton` prop，未来故事可直接使用 `<RaceCard skeleton />` 渲染骨架屏。
- `HorseSearchSelect.vue` 使用 `defineModel<Horse[]>('selectedHorses')` 实现 v-model 双向绑定 — 新增组件应优先使用 `defineModel` 替代手动 `emit('update:...')` 模式。
- `HorseDetailCard.vue` 用于展示马匹快照数据（马柱卡片），接收 `snapshotData` prop（可空，通过 `withDefaults` 提供默认值）。**桌面与移动端共用同一套响应式布局**（不再是隐藏的 `<table>` + 单独的移动端四行布局）：左侧主徽章（有名次时显示名次「N着」金/银/铜，否则显示闸位号，传 `fieldSize` 时用 JRA 枠色）；中间名字行（拖拽手柄、马名、名次模式下的闸位小色块、性龄 chip、所属地）+ 两列对齐的事实区（骑手 / 血统「父 × 母父」/ 前走 / 主胜），前走名次从文本里拆成彩色 chip（1-3 着金银铜、4-5 着绿、除外红）；右侧为投票 pill（「选它」/「✓ 已投」，可悬停设备上悬停显示「取消」）和管理员图标按钮。投票 pill 只是视觉提示（`aria-hidden`），整张卡片仍是 `role="button"`。移动端事实区单列且允许换行，并保留 `touch-action: manipulation; -webkit-touch-callout: none; user-select: none;`。
- `HorseDetailCard.vue` 的管理员操作（仅 `editable` 时显示，位于卡片右侧）：↻ 刷新按钮 → 确认弹窗（Teleport to body）→ emit `refresh`；🗑 移除按钮（`desktop-only`，emit `deleteClick`，移动端仍用抖动模式角标 ✕）。骑手可通过 ✎ 按钮、桌面双击或移动端点击进入内联编辑，输入框通过模板 ref 聚焦（旧实现用 `document.querySelector('.inline-input')`，移动端会聚焦到隐藏的桌面输入框）。
- `StatusBadge.vue` 用于展示比赛状态胶囊：voting（品牌绿渐变 + 呼吸圆点）、locked（灰底 `--color-ink-muted` + SVG 锁）、settled（深绿底 + SVG 勾）。接收 `status: string` prop。
- `ConfirmDeleteModal.vue` 可复用确认弹窗组件（不仅限删除），接收 `title`, `itemName`, `message`, `loading`, `confirmText`（默认"确认删除"）, `loadingText`（默认"删除中…"） props，emit `confirm` / `cancel`。使用 `<Teleport to="body">` + `role="dialog"` + `aria-modal` + Esc 关闭 + 遮罩层点击关闭。不可点击遮罩层外部关闭（防误触）。`RaceDetailPage.vue` 中锁定比赛也复用此组件，传入 `confirm-text="确认锁定"` `loading-text="锁定中…"`。
- `HomePage.vue` 中弹窗选"自定义"等级时显示正序积分列表和扣分规则输入框，创建比赛时附带 `custom_scoring` 字段。创建比赛弹窗（`.modal-backdrop`）不可点击遮罩层外部关闭（无 `@click.self`），仅能通过"取消"按钮关闭。radio 单选框 CSS 使用 `clip: rect(0,0,0,0)` 而非 `width:0;height:0`，避免点击 `<label>` 不触发 v-model 更新。`HorseDetailCard.vue` 的 `<table>` 内 `<tr>` 必须包在 `<tbody>` 中。`RaceHeaderEditor` 只编辑比赛名称，日期在详情页 `race-subinfo` 中双击编辑。
- `HorsesPage.vue`（马匹管理页）添加/编辑马匹弹窗使用 `<Teleport to="body">` + `.modal-overlay`，不可点击遮罩层外部关闭（无 `@click.self`），仅能通过"取消"按钮关闭。
- 全局 `@keyframes skeleton-shimmer` 定义在 `base.css` 中，所有骨架屏复用此动画。

**Python/FastAPI:**
- Files and variables: **snake_case** (`get_current_user`, `race_service.py`)
- DB table names: **snake_case plural** (`users`, `races`, `horses`, `votes`)
- All endpoints/services use `async def` — no sync endpoints
- API prefix `/api/v1/` for all endpoints
- Response format: success `{"data": ...}`, error `{"detail": {"code": "ERROR_CODE", "message": "..."}}`
- Endpoints only orchestrate — all business logic in `services/`
- DB session via `Depends(get_db)` from `deps.py`
- SQLAlchemy model columns use `mapped_column` type annotations
- pytest: `asyncio_mode = auto` in pyproject.toml

### Framework-Specific Rules

**Vue 3:**
- All components: `<script setup lang="ts">` Composition API
- Styles: **scoped CSS** + CSS custom properties (no UI library)
- Layout components in `src/layouts/`, page components in `src/pages/`, reusable components in `src/components/`
- Composable functions in `src/composables/` (`useAuth.ts`, `useVote.ts`, `useDragSort.ts`)
- Admin routes prefixed `/admin/`, sharing `AppLayout` with all other pages. No separate layout — admin nav is in a dropdown menu. Admin nav items: 马匹管理, 用户管理.
- Auth guard implementation in `router/index.ts`: `beforeEach` with `useAuthStore()` guards admin routes (`isAdmin`), auth-required routes (`requiresAuth`), and guest-only pages (login/register/reset-password).
- **RouteMeta must be extended** for custom meta fields used in guards: add `declare module 'vue-router' { interface RouteMeta { requiresAuth?: boolean; isAdmin?: boolean } }` in router/index.ts. This avoids `as Record<string, unknown>` type assertions.
- Guest page name list (`guestPageNames: string[]`) extracted to module-level constant in router/index.ts — NOT defined inside beforeEach.
- `@` path alias configured in both `vite.config.ts` and `tsconfig.app.json` — use `@/pages/`, `@/components/`, etc.
- Responsive navigation via `AppLayout` (rendered by `App.vue`; **AppLayout owns the `<RouterView>`**): desktop top nav (≥768px, `--gradient-brand` bg + gold bottom line, `position: fixed`, gains a shadow once `.scroll-container` scrolls) and mobile bottom nav (<768px, frosted glass, active item gets a pill behind the icon). On desktop, a `.scroll-container` (`position: fixed; top: var(--header-height); left: 0; right: 0; bottom: 0; overflow-y: auto`) handles scrolling below the fixed header, preventing scrollbar-induced horizontal layout shift. Page changes go through `<Transition name="page" mode="out-in">` keyed by `route.path` (so `/races/1` → `/races/2` remounts) and `@before-enter` resets the scroll container to the top. The page transition is **opacity-only** — a transform on the page root would become the containing block for the page's `position: fixed` FAB / scroll hints. Admin users see a "管理" dropdown trigger in both navs. Admin pages share the same AppLayout — no separate layout wrapping.
- `safe-area-inset-bottom` applied via `viewport-fit=cover` meta + CSS `env(safe-area-inset-bottom)` — always add to mobile fixed elements
- `prefers-reduced-motion: reduce` respected globally in `base.css` — overrides all animations/transitions. 全局 `scroll-behavior: smooth` 也被覆盖为 `auto`。
- `*:focus-visible` 全局统一样式在 `base.css` 中定义（2px 竞马绿 outline + 2px offset），所有可聚焦元素自动继承。组件内如需自定义 focus 样式，使用 scoped CSS 覆盖。
- **ARIA combobox 模式**：搜索下拉组件（如 `HorseSearchSelect.vue`）必须遵循 combobox 无障碍模式：`role="combobox"` + `:aria-expanded="showDropdown"`（动态绑定，不能硬编码 `"false"`）+ `aria-controls` 指向 listbox + `role="listbox"` + `role="option"` + `aria-selected`。`aria-expanded` 必须响应式绑定到下拉展开状态。
- Admin nav in `AppLayout`: desktop header nav-links and mobile bottom nav both have a "管理" dropdown trigger. Dropdown shows 马匹管理/用户管理 (原邀请码). Closes on click-outside, Escape, and route change. Desktop dropdown drops downward; mobile dropdown rises upward from bottom bar, with `top: auto` override to avoid CSS cascade conflict from `.admin-dropdown` default `top` value. Mobile bottom nav also includes login/logout auth items: `<router-link to="/login">` for login, `<div @click="handleLogout">` for logout (exit-door icon + "退出" label).

**FastAPI:**
- App entry: `app/main.py` with `lifespan` for DB engine lifecycle
- Config: `app/core/config.py` via Pydantic Settings (reads from `.env`)
- Dependencies: `app/api/deps.py` — `get_db` (session), `get_current_user` (queries DB → User ORM), `get_current_admin` (requires admin)
- Auth check: `get_current_user` returns `None` for guests (no token), raises `TOKEN_EXPIRED` for expired tokens, `INVALID_TOKEN` for invalid tokens, `NOT_AUTHENTICATED` for valid token but user not found in DB. Returns full `User` ORM object.
- Admin check: `get_current_admin` depends on `get_current_user`, checks `user.is_admin` ORM property, raises 403 `FORBIDDEN` for non-admins
- Auth endpoints: `POST /api/v1/auth/login` (returns access_token + refresh_token + user), `POST /api/v1/auth/refresh` (returns new access_token from valid refresh_token). Both unauthenticated.
- Race endpoints (`endpoints/races.py`): `GET /api/v1/races` (public, list), `GET /api/v1/races/{id}` (public, detail with snapshots), `POST /api/v1/races` (admin, create), `PATCH /api/v1/races/{id}` (admin, edit only voting), `DELETE /api/v1/races/{id}` (admin, non-settled only), `POST /api/v1/races/{race_id}/horses` (admin, add horse), `DELETE /api/v1/races/{race_id}/horses/{race_horse_id}` (admin, remove horse from race, only voting state, rejects if horse has votes), `POST /api/v1/races/{race_id}/horses/{race_horse_id}/refresh-snapshot` (admin, refresh snapshot from latest Horse data).
- Endpoints: `app/api/v1/endpoints/` — one file per domain (auth, races, horses, votes, results, leaderboard, admin)
- API router: `app/api/v1/__init__.py` creates the APIRouter and includes all endpoint routers; `main.py` calls `app.include_router(api_v1_router)`
- Business logic: `app/services/` — one service per domain; uses `db.flush()` + `get_db` auto-commit pattern
- Data models: `app/models/` — SQLAlchemy declarative models extending `Base`
- **CRITICAL**: `models/__init__.py` MUST import `Base` from `app.core.database`, NOT redefine it. Alembic `env.py` uses `from app.core.database import Base` as its metadata source — duplicate Base classes cause migrations to miss models.
- CORS: configured in `main.py` (TODO: tighten for production deployment)

### Testing Rules

**Backend (pytest):**
- Config: `asyncio_mode = auto` in `pyproject.toml`, `testpaths = ["tests"]`
- Test directory: `backend/tests/`, one file per domain (`test_scoring_engine.py`, `test_auth.py`, etc.)
- `conftest.py` provides shared fixtures:
  - `db_session` — in-memory SQLite engine (`sqlite+aiosqlite:///:memory:`) with `StaticPool`, tables created via `Base.metadata.create_all`, engine disposed after each test
  - `async_client` — `httpx.AsyncClient` with `ASGITransport` pointing to the app, `get_db` overridden with `db_session`. Automatically clears `dependency_overrides` after each test
- For new test files, import shared fixtures from `conftest.py`; for API integration tests, use `async_client` fixture to automatically get DB injection
- Scoring engine (`scoring_engine.py`) must be pure function, zero external dependencies — unit test only
- HTTP integration tests use `httpx.AsyncClient` with FastAPI's `TestClient`
- All async tests run with `pytest-asyncio`

**Frontend (vitest):**
- Not yet configured — planned for future stories
- Test file convention: `src/__tests__/{name}.test.ts`

**Coverage expectation:**
- Scoring engine: 100% branch coverage for all 4 rule types (G1, G2, 2Y-G1, custom) + edge cases
- Service layer: cover all business logic paths (CRUD, search, error branches)
- Endpoint layer: integration tests for main flows + error cases (use dependency overrides for auth)

### Code Quality & Style Rules

**Naming conventions (must follow):**

| Scope | Convention | Example |
|-------|-----------|---------|
| Python files/variables | snake_case | `get_current_user()`, `auth_service.py` |
| Database table names | snake_case plural | `users`, `races`, `horses`, `votes` |
| DB columns / foreign keys | snake_case | `user_id`, `race_name`, `created_at` |
| TS/Vue component files | PascalCase | `RaceCard.vue`, `AdminLayout.vue`, `InviteCodeTable.vue` |
| TS non-component files | camelCase | `useAuth.ts`, `apiClient.ts`, `authStore.ts` |
| TS functions/variables | camelCase | `getUserData()`, `currentUser` |
| Pinia stores | `use{Name}Store` | `useAuthStore`, `useRaceStore` |
| CSS custom properties | kebab-case | `--color-primary`, `--spacing-4` |
| API endpoints | plural REST | `/api/v1/races`, `/api/v1/horses` |
| API JSON fields | snake_case (frontend & backend consistent) | `user_id`, `race_name` |

**Code organization:**
- Backend: `endpoints/` (HTTP orchestration only) → `services/` (business logic) → `models/` (data models)
- Frontend: `pages/` → `components/` → `composables/` + `stores/` + `api/` + `types/`
- Styles separated into `variables.css` / `base.css` / `utilities.css`
- API calls encapsulated in `src/api/` — one file per domain
- TypeScript types in `src/types/` — one file per domain

**Dates:** ISO 8601 strings (`2026-06-09T15:00:00Z`)
**Null handling:** Use `null`, never empty strings or omitted fields

### 自动化验证

- 前端 `pnpm test` 执行原有 Node 回归和 Vitest DOM 测试，`pnpm run test:typecheck` 检查测试类型；不要让 Vitest 收集 `tests/regressions.test.mjs` 的 Node 用例。DOM 测试不代表真实浏览器视觉验收。
- PostgreSQL 用例位于 `backend/tests/postgres/`，标记 `postgres`；仅使用显式 `TEST_DATABASE_URL`（数据库名以 `_test` 结尾），每例使用独立随机 schema。不得复用实际应用数据库或执行数据库级清空。`compose.test.yml` 端口55432、项目名guess-tests，与应用容器隔离。
- Alembic 支持通过 `config.attributes['connection']` 传入连接，供集成测试在隔离 schema 执行真实迁移。
- Windows `scripts/test.ps1` 支持 `-PythonExe` 和 `-IncludePostgres`，仅清理由本次脚本启动的测试容器；CI配置为 `.github/workflows/tests.yml`。
- passlib1.7的测试/安装依赖限定bcrypt4.0.x；升级依赖时必须在干净Python3.12环境验证认证测试。

### Development Workflow Rules

**Git:**
- Repo initialized with initial commit `9e8be22` — `feat: project initialization scaffold`
- `.gitignore` excludes: `node_modules/`, `__pycache__/`, `.env`, `*.pyc`, `venv/`, `.vscode/`, `.idea/`, `dist/`, `.DS_Store`
- Story-driven: each story flows `backlog` → `ready-for-dev` → `in-progress` → `review` → `done`
- **Branch + PR workflow**: never commit features directly to `master`. Create a short-lived branch (`feat/`, `fix/`, `refactor/`, `docs/`, `test/` + kebab-case), push to `origin`, open a PR against `master`, merge (squash) only after `.github/workflows/tests.yml` passes. Full rules in root `AGENTS.md`.

**Local development:**
- PostgreSQL: `docker compose up -d` (port 5432)
- Backend: `cd backend && uvicorn app.main:app --reload` (port 8000)
- Frontend: `cd frontend && pnpm dev` (port 5173)
- API proxy: frontend Vite proxies `/api` → `http://localhost:8000`
- API docs: `http://localhost:8000/docs` (Swagger UI)

**Production deployment:**
- VPS + Docker Compose (Nginx reverse proxy + API + PostgreSQL)
- Config via `.env` + Pydantic Settings
- CI: GitHub Actions `.github/workflows/tests.yml` (runs on push and pull_request)

### Critical Don't-Miss Rules

**Anti-patterns (must NOT do):**
- Endpoints must NOT contain business logic — delegate to `services/`
- Do NOT convert API fields to camelCase on frontend — keep snake_case consistent
- Do NOT use sync endpoints — all FastAPI endpoints must be `async def`
- Do NOT add external UI libraries — use custom JRA components + CSS variables
- Do NOT use WebSocket/SSE — poll or optimistic updates only
- Do NOT implement OAuth/3rd-party login — username + password + invite code only
- Do NOT implement dark mode — v1 is light mode only
- Admin routes are top-level routes (no child layout) — they share `AppLayout` with all other pages. The nav bar has a "管理" dropdown for admin sub-navigation.
- Do NOT use `!important` globally except in utility classes (`.hidden`, `.mobile-only`, `.desktop-only`), reduced-motion override, and date-input `::-webkit-datetime-edit` shadow DOM hiding (needed to override browser default styles)
- **Do NOT import `useAuthStore` in `client.ts`** because authStore already depends on api/auth.ts and client.ts. The request interceptor reads auth from **localStorage**. Pinia syncs via `persistAuth()`, `clearAuth()`, `restoreSession()`, and the events in `utils/authEvents.ts`. The client proactively refreshes expired or nearly expired access tokens within 5 seconds of expiry and can retry once after a 401. Concurrent refreshes share a request within the same session. Each login gets a new session ID, with the refresh token serving as the identifier for older sessions. A request cancels when its session changes during refresh or before a retry. A refresh failure preserves the session unless the API returns `401 INVALID_REFRESH_TOKEN`. Known expired refresh tokens also clear auth and redirect to `/login?session=expired`. Guest pages and auth endpoints skip the refresh and redirect flow.
- Do NOT use bare `catch` blocks on async functions — always use `catch (err)` to enable error differentiation. Future stories should follow the async/await + structured error handling pattern.
- Do NOT duplicate `@keyframes skeleton-shimmer` in component scoped styles — use the global animation from `base.css` instead.

**Security:**
- JWT secrets (`SECRET_KEY`, `JWT_SECRET`) MUST be changed from defaults before production
- CORS must be tightened for production (methods, headers)
- Login failure returns generic error: `"用户名或密码错误"` — no field-specific leak. However, LoginPage.vue catch block also handles Network Error (→ "网络错误，请重试"), 422 validation errors (→ field-level messages), and 500 (→ "服务器错误，请稍后重试").
- Passwords hashed via bcrypt (passlib CryptContext)
- Guests are read-only — voting requires authentication
- Admin seed account: `app/utils/seed.py` creates default admin (username: `admin`, password: `admin123`, `is_admin=True`, `invite_code=None`) on app startup. Idempotent — skips if already exists. Protected with `IntegrityError` guard for concurrent startup.

**Performance:**
- No Redis/cache layer needed for v1 — direct DB queries suffice for ~100 users
- Route lazy loading configured (Vite auto-splits)
- No virtual scroll needed

**Edge cases:**
- Race horse data uses **snapshot** mechanism — horse attributes at creation time are frozen in `RaceHorse.snapshot_data` JSON. Race detail pages read from snapshot_data, NOT the live Horse table. Editing a race does NOT update existing snapshots; new horses added via edit get fresh snapshots at add time.
- Race status machine: `voting` → `locked` → `settled` (one direction). Only `voting` races are editable. `locked` races block voting. `settled` races are final (can only modify results).
- Race grade replaced with **6-tag system**: `age_range`（2岁/2+岁/3岁/3+岁/4+岁/其他）, `sex_restriction`（无/牝限/牡牝限/牡限）, `race_grade`（G1/G2/JPN1/其他/自定义）, `country`（日本/英国/美国/.../其他）, `distance`（正整数米数，如 `1200`，前端展示拼接 `m`）, `surface`（草地/泥地/全天候/障碍/其他）。Custom scoring 只在使用 `race_grade="自定义"` 时生效，格式: `{"positive_scores": [10,7,5,3,2,1], "penalty_rules": [{"position": -1, "points": -5}]}`。旧 `GradeEnum` 已移除。`sex_restriction` 为"无"时前端不渲染对应 tag。
- Settled races cannot be deleted — only result modification with full rollback/recalculate. `voting` 和 `locked` 状态的比赛可以删除（含级联删除投票记录）。删除操作需要管理员权限和二次确认弹窗，使用 `ConfirmDeleteModal` 组件。
- `HomePage.vue` 底部悬浮按钮创建比赛（管理员可见），带有弹窗。管理后台通过首页管理入口旁的下拉菜单访问。
- DNF/scratched horses score 0 points and are excluded from deduction calculation denominators
- Custom scoring rules apply only to the current race — not saved as templates
- Password reset uses **invite_code** only (no username needed) — looks up the activated non-admin user (`User.invite_code == code`, `User.is_admin == False`, `User.password_hash.isnot(None)`). All failure cases (including unactivated/pending invite codes) return the same `INVITE_CODE_MISMATCH` error to prevent user enumeration. ResetPasswordPage is a single-step form (invite_code + new_password).
- **邀请码与用户单表模型（无独立 `invite_codes` 表）**：
  1. **单表生命周期**：`users` 表合并管理邀请码与账户（`qq` 全局非空唯一 `ix_users_qq`，`invite_code` 可空唯一 `ix_users_invite_code`，`username` 可空唯一 `ix_users_username`，`password_hash` 可空）：
     - 管理员：`is_admin=True, username='admin', password_hash='<hash>', invite_code=None`
     - 待注册邀请码（`unused`）：`is_admin=False, username=None, password_hash=None, invite_code='XXXXXXXX'`
     - 历史成绩占位用户（`unused` + 占位）：`is_admin=False, username='<name>', password_hash=None, invite_code='XXXXXXXX'`（`is_placeholder()` 判定：`not user.is_admin and user.password_hash is None and user.username is not None`）
     - 已注册正式用户（`used`）：`is_admin=False, username='<name>', password_hash='<hash>', invite_code='XXXXXXXX'`
  2. **注册校验 QQ**：`register()` 校验邀请码关联行的 `user.qq == request.qq`，不匹配返回 `QQ_MISMATCH`；已激活账户返回 `INVITE_CODE_INVALID`；原地填充 `username` 与 `password_hash` 激活该行（保留原 `user.id`）。
  3. **管理员删除级联**：`DELETE /api/v1/admin/invite-codes/{code}` 删除待用码行，或级联删除已注册用户 + 投票（`votes.user_id` CASCADE）+ 历史成绩（`historical_scores.user_id` CASCADE）。占位用户的邀请码不可删除（409 `PLACEHOLDER_PROTECTED`）。
- **邀请码状态**：仅 `unused`（`password_hash is None`）与 `used`（`password_hash is not None`）两种派生状态（已移除 `disabled` 状态）。
- **登录三种模式**（`LoginRequest` 所有字段可选，按优先级判断）：`invite_code`（无密码，查 `User.invite_code` 登录；`password_hash is None` 返回 `"该邀请码尚未绑定用户"`）/ `qq`（+密码查 `User.qq`）/ `username`（+密码查 `User.username`）。不存在或未设密码的账户返回 `"用户名或密码错误"`。

**Voting System 模式（Story 3.2）：**
- Vote 模型：`(user_id, race_id)` 唯一约束实现一用户一票一赛。`race_horse_id` FK 指向 `race_horses.id`（**无** CASCADE——防止编辑比赛移除马匹时静默删除投票）。`user_id` 和 `race_id` FK 有 CASCADE（用户删除或比赛删除时级联清理）。
- **投票 Upsert 防竞态模式**：`vote_service.create_or_update_vote()` 使用 SELECT → check → INSERT/UPDATE 模式，外层包裹 `try/except IntegrityError`。当并发请求同时通过 SELECT（均未找到现有投票）时，第二个 INSERT 触发唯一约束冲突，`IntegrityError` 被捕获后回滚并重试 SELECT → UPDATE，返回 200。此模式替代 `ON CONFLICT DO UPDATE`（SQLAlchemy async + SQLite 测试兼容性考量）。
- **Post-vote eager-load 模式**：`create_or_update_vote()` 在 `flush()` + `refresh()` 后，额外执行一次带 `selectinload(Vote.race_horse_rel)` 的查询以解析马名。端点层不再单独调用 `get_race_votes()`（避免 N+1 和冗余查询）。
- **Lock 操作模式**：`POST /api/v1/races/{race_id}/lock` 为管理员专用端点（`Depends(get_current_admin)`）。使用否定检查 `if race.status != RaceStatus.VOTING`（而非列举非目标状态）以确保未来状态扩展的健壮性。仅 `voting` 状态可锁定。
**取消投票端点模式**：`DELETE /api/v1/races/{race_id}/votes` 为已登录用户专用端点。校验比赛处于 `voting` 状态后才能取消，通过 `await db.delete(vote)` + `flush()` 删除投票记录。服务层 `delete_vote()` 封装所有校验逻辑（比赛存在性、比赛状态、投票是否存在）。
**可选用户依赖模式**：`get_optional_user()` 用于公开端点中可选地展示用户/管理员特定数据（如 `list_races` 的 `has_voted` 与隐藏比赛可见性、`get_race` 的隐藏比赛访问）。无 Authorization 头时返回 `None`（游客访问）；**携带了已过期/无效/已删除用户的 Bearer Token 时委托 `get_current_user` 抛出 401**（严禁静默吞掉异常返回 `None`，否则管理员在 access_token 30 分钟过期后会被当成游客返回 200/404，导致隐藏比赛丢失且无法触发前端 401 自动续期）。
- **编辑比赛防删票保护**：`race_service.update_race()` 在移除马匹时，先查询 `Vote` 表检查被移除的 `race_horse_ids` 是否存在投票。若有投票存在，返回 400 `HORSE_HAS_VOTES` 拒绝操作。此保护覆盖 Story 3.2 中移除的 race_horse_id FK CASCADE 限制（无 DB 级 CASCADE，改由应用层保护）。

**Service & DB patterns:**
- **9 核心业务表架构与基线迁移**：全库精简为 9 张业务表（`users`、`horses`、`races`、`race_horses`、`votes`、`historical_import_batches`、`historical_import_changes`、`historical_races`、`historical_scores`），已移除 `invite_codes`、`horse_auto_update_logs`、`score_change_logs` 三张表及所有表上的 `updated_at`、`horses.created_at`、`horses.manually_updated_fields`、`races.creator_id`、`race_horses.weight`、`race_horses.created_at`。Alembic 迁移已压平重建为单一基线脚本 `backend/alembic/versions/001_initial_schema.py`（`revision = "001"`），PostgreSQL 集成测试通过 `compare_metadata` 强制校验 ORM 与迁移零差异。
- `flush()` 后必须调用 `refresh()` 才能读取含 `server_default` 的字段值（如 `created_at`），否则 Pydantic `model_validate()` 会报 `MissingGreenlet` 错误。所有 CRUD 服务的 create/update 方法必须遵循 `flush()` → `refresh()` → return 模式。
- Pydantic schemas：PATCH endpoint 使用的 Update schema（如 `HorseUpdate`）必须包含与 Create schema（如 `HorseCreate`）相同的 `@field_validator`，包括 `.strip()` 处理——因为用户可通过 API 直接调用 PATCH 绕过前端校验。
- **PATCH 防 null 覆盖模式**：在 `update_race` 等 PATCH 服务中，`data.model_dump(exclude_unset=True)` 后必须过滤 `None` 值：`update_data = {k: v for k, v in update_data.items() if v is not None}`（仅显式支持清空的字段如 `RaceHorseUpdate.jockey` 例外）。前端编辑应通过差异检测**仅发送变更的字段**。
- **前走字段结算直写模式**：已移除 `auto_update_service.py`、`Horse.manually_updated_fields` 与 `POST /api/v1/horses/{id}/reset-auto-protection`。`result_service.submit_results()` 结算时按 `race.date >= prev_date` 日期比较直接更新 `Horse` 表的 `previous_result`、`previous_result_date`、`previous_result_position`。
- **Race 状态约束约定**：不使用 PostgreSQL 原生 `ENUM` 类型；`races.status` 使用小写 `VARCHAR(20)` + `CHECK (status IN ('voting', 'locked', 'settled'))`（约束名 `ck_races_status`，`server_default='voting'`），ORM 层使用 `StrEnum` + `native_enum=False`。

**Scoring Engine 纯函数模式（Story 3.1）：**
- `scoring_engine.py` 必须是纯函数模块，零外部依赖，仅允许 `from typing import Any`。禁止导入 FastAPI、SQLAlchemy 或任何 DB 相关模块。
- 公共 API：`calculate_score(grade: str, total_horses: int, position: int, custom_scoring: dict | None = None) -> int`
- 新增 `derive_scoring_grade(age_range: str, race_grade: str) -> str` 将 5-tag 映射到 4 种评分模式：`"2岁"+G1→YOUNG_G1`、非G1/非自定义→G2_JPN1、自定义→CUSTOM、其他→G1。结算时调用 `calculate_score(grade=derive_scoring_grade(...))`。
- G1 扣分使用**绝对位置转换公式**：`penalty_position = total_horses + offset + 1`，其中 `offset` 为负数（-1=最后一名，-2=倒数第二名，依此类推）。
- G1 扣分分档：≥8匹扣末3名(-10/-5/-1)、7匹扣末2名(-5/-1)、6匹扣末1名(-1)、≤5匹无扣分。
- G2_JPN1：正分 +5/+3/+1（仅前三名），不扣分。
- YOUNG_G1：正分同 G1（+10/+5/+3/+2/+1），不扣分。
- CUSTOM：从 `custom_scoring` 字典读取 `positive_scores`（list[int]，1-indexed）和可选的 `penalty_rules`（list[dict]，position 为负偏移，points 为扣分值）。若某名次同时有正序积分和扣分，则**加分优先**（豁免扣分），与 G1 原则一致——一个名次不会既加分又扣分。
- DNF/退赛：`position <= 0` 返回 0 分。
- 调用方负责过滤 DNF 马匹（不将其计入 `total_horses`）——引擎不做 DB 查询。
- 评分模式的 grade 字符串值：`"G1"`, `"G2_JPN1"`, `"YOUNG_G1"`, `"CUSTOM"`。
- 100% 分支覆盖要求：测试必须覆盖 4 种等级的所有边界组合，包括 G1 的 4 种匹数分档（≥8/7/6/≤5）。

**Frontend patterns:**
- 管理后台 CRUD 页面使用 `<Teleport to="body">` 模态框进行创建/编辑操作，搜索框使用 300ms 防抖（`watch(search, debouncedSearch)` + `setTimeout`）。**搜索不能把页面切回 loading 态**——那会卸载搜索框导致输入中途失焦，空结果还会被当成「库为空」并丢失搜索框；改为 `loadXxx({ quiet: true })` 只置 `searching`，保留列表并降低透明度，空结果显示「没有找到…」+ 清空搜索。删除一律用 `ConfirmDeleteModal`，不用原生 `confirm()`；删除失败用页内横幅提示（`showNotice`），不要写进只在 error 态渲染的 `errorMessage`。列表在 <768px 时把 `<table>` 行转成卡片（`td[data-label]::before` 显示列名），不再横向滚动。
- **PATCH 编辑模式的关键模式**：`handleSave` 在编辑时必须按字段逐一比较当前值与原始值的差异，**仅发送变更的字段**，而非发送所有字段为 `null`。否则后端 `exclude_unset=True` 无法区分"用户未修改"和"用户将某字段清空为 null"——发送 `null` 会覆盖数据库中的已有值。参考实现：`frontend/src/pages/admin/HorsesPage.vue` 中的 `handleSave`。
- 新建数据后不推荐 `unshift`，应 `push` 后按显示顺序 `sort()` 避免与后端排序不一致导致的视觉跳跃。
- **HorseSearchSelect 点击即选模式**：搜索下拉选中马匹后立即关闭下拉框并清空搜索词（`showDropdown = false` + `searchText = ''`），而非在下拉框中打钩多选。点击行为为**追加模式**（`selectedHorses = [...selectedHorses, horse]`），已选马匹不会重复添加。通过上方 tag 展示已选列表，配合父组件的"添加"按钮一次性提交。
- **移动端触控安全模式**：
  - `:draggable` 属性在桌面端保持 `:draggable="draggable ? true : undefined"`；在移动端组件内通过 `window.matchMedia('(max-width: 767px)')` 检测后强制设为 `false`，避免 HTML5 原生拖拽在触控浏览器中与自定义 touch 排序冲突或引发长按冻结。
  - 移动端 touch 事件通过 **函数内守卫** 而非模板拆分控制——admin voting 使用单一 `<template v-if="isAdmin && isRaceVoting">`，`handleGateTouchStart` 等函数在 `!isJiggleMode.value` 时立即 `return` 无副作用。避免模板拆分导致 Vue 重建 DOM 破坏桌面端 DnD 状态。
  - 移动端 `.gate-drag-item`、`.result-drag-item` 必须设置 `touch-action: manipulation` 以抑制 `draggable="true"` 属性触发的浏览器原生长按拖拽。
  - 所有 touch 事件处理 `@touchend` 必须配套 `@touchcancel`（系统级长按/OS 手势抢占时触发）。
  - **禁止**在 touch 处理器中设置 `document.body.style.overflow = 'hidden'`——该全局状态在 DevTools 模拟或系统 touchcancel 下无法可靠恢复。改用 CSS `touch-action: none` 阻止拖拽期间滚动。
- **Date input 原生占位文字隐藏模式**：`<input type="date">` 在中文 locale 下浏览器显示 "yyyy/mm/dd" 原生占位文字。解决方案：在 `base.css` 中全局定义 `input[type="date"].is-empty::-webkit-datetime-edit { visibility: hidden !important; }` + `input[type="date"].is-empty:focus::-webkit-datetime-edit { visibility: visible !important; }`，每个 date input 添加 `:class="{ 'is-empty': !modelVar }"` 让 Vue 响应式追踪空值状态。空值未聚焦时隐藏，聚焦或已有值时正常显示。
- **CSS 变量使用规范**：`variables.css` 中定义的 spacing 变量名称为 `--spacing-{N}`（N×4px，如 `--spacing-1`=4px、`--spacing-2`=8px、`--spacing-3`=12px、`--spacing-4`=16px、`--spacing-5`=20px、`--spacing-6`=24px、`--spacing-8`=32px、`--spacing-10`=40px、`--spacing-12`=48px、`--spacing-16`=64px）。**不存在** `--spacing-20`、`--spacing-24`、`--spacing-32` 等变量，使用这些不存在的变量会导致整个 CSS 声明失效。页面排版错乱时优先检查是否引用了不存在的 spacing 变量。
- **Auth session expiry handling**：`main.ts` 在注册路由前调用 `authStore.restoreSession()` 确保首屏与路由守卫立即拿到登录态。`authStore` 解析 refresh token 的 `exp` 声明设置 `setTimeout`（上限钳制 `2_147_483_647` ms 防 32 位整数溢出），并在窗口 `focus`、页面 `visibilitychange`（处理电脑休眠/后台标签页唤醒）及跨标签页 `storage` 事件时重新同步 `localStorage` 与校验到期；管理员会话到期后清除登录态并跳转到 `/login?session=expired`。`LoginPage.vue` 读取 `route.query.session === 'expired'` 显示"登录状态已过期，请重新登录"。JWT 工具位于 `frontend/src/utils/jwt.ts`，无环状态同步位于 `frontend/src/utils/authEvents.ts`。
- **滚动条偏移防护模式**：`.scroll-container`（`AppLayout.vue` 桌面+移动端媒体查询）使用 `scrollbar-gutter: stable`——始终预留滚动条空间，防止内容高度跨越滚动阈值时触发水平布局偏移。`html` 添加 `overflow: hidden`（`base.css`）兜底——所有页面内容渲染在 `position: fixed` 的 `.scroll-container` 内，body 级别永不出现滚动条。
- **Axios 数组参数序列化模式**：axios v1.x 默认将数组参数序列化为 bracket notation（`country[]=日本`），FastAPI `Query(list[str])` 只识别 repeated-key 格式（`country=日本&country=美国`）。在 `client.ts` 的 `axios.create()` 中添加 `paramsSerializer`：数组值用 `forEach` 生成重复 key（`encodeURIComponent(key)=encodeURIComponent(v)`），其他值正常编码。所有通过 `apiClient` 发起的请求自动使用此格式，无需每个调用处手动处理。

**VoteButton 状态机（Story 3.3）已迁移为卡片点击投票模式：**
- `VoteButton.vue` 已被移除，改为 `HorseDetailCard.vue` 直接支持点击投票
- `HorseDetailCard.vue` 新增 `votable`、`voted`、`submitting` props：`votable` 时显示 `cursor: pointer` + hover 上浮、右侧「选它」pill；`voted` 时显示金色边框 + 光晕 + 扫光动画，pill 变为金色「✓ 已投」；`submitting` 时 pill 显示 spinner 并禁用点击
- 移动端不再有固定底部投票栏（`position: fixed; bottom: 0`）——投票交互直接在卡片上进行
- 锁定/已结算状态：通过 `.voted-horse-locked` CSS 类（金色边框）在 HorseDetailCard 上高亮用户投中的马匹

**useVote composable 模式（Story 3.3）：**
- `toggleVote(horse, raceId)` 替代旧的 `selectHorse` + `enterSelectionMode` 模式，实现三段逻辑：
  - **未投票** → 提交投票（`POST /races/{id}/votes`）
  - **已投该马再次点击** → 取消投票（`DELETE /races/{id}/votes`）
  - **已投他马点击新马** → 切换投票（`POST` 更新）
- 移除 `isInSelectionMode`、`enterSelectionMode`、`exitSelectionMode` 状态
- 新增 `votedRaceHorseId` 响应式字段追踪已投票马匹 ID，用于判断"是否同一匹马"
- 乐观更新模式：投票/取消均先乐观更新状态，API 失败时回滚
- 组件卸载保护：`let unmounted = false` + `onUnmounted(() => { unmounted = true })`，所有 `await` 后的状态更新前检查 `if (unmounted) return`

**RaceDetailPage 投票集成模式（Story 3.3）：**
- **移除** VoteButton、HorseSelectCard 引用；**移除** 选择模式（`selection-section`）、**移除** 底部投票栏（`vote-bar`）
- 比赛详情页中的赛马卡片（HorseDetailCard）直接可点击投票——点击卡片 = 投票/取消/切换
- 游客点击卡片 → 跳转登录页；管理员不可投票。为此 `cardsVotable = isRaceVoting && !isAdmin`（**包含游客**），由 `handleCardClick` 判断未登录时跳转——旧条件里多了 `isLoggedIn`，导致游客点击毫无反应。
- 新增投票提示条（`vote-hint`）：引导用户操作
- VotingDetail 组件使用 Chart.js Doughnut 环形图展示投票分布：马匹按票数降序排列（图与图例同序同色），环心显示总票数（count-up），Chart.js 自带 legend 关闭，改为自定义图例列表（色块 + 票数/占比 + 增长进度条 + 投票人名单），悬停图例行会联动高亮对应扇区。悬停扇区 tooltip 显示票数/百分比和投票人名单。已结算比赛通过 `horsePositions` prop 传入冠军信息，冠军马扇区显示金色边框 + 偏移，图例显示「🏆 冠军」。所有比赛状态（voting/locked/settled）均显示投票分布。刷新策略：仅在页面加载和投票成功后刷新，无轮询。依赖：`chart.js ^4.5.1` + `vue-chartjs ^5.3.3`（只注册 ArcElement + Tooltip）。
- HorseSelectCard 已被删除，无单选组需求——每张卡片独立可点击

**HomePage 首场比赛列表投票状态模式：**
- **移除**"投票"按钮（原金色 `vote-entry` CSS 类）
- **新增** `vote-status` 徽章，仅在 voting 状态 + 已登录时显示用户的投票状态："未投票"（浅金底 + 呼吸圆点提醒）/"已投票"（浅绿底 + SVG 勾）
- 未登录用户不显示任何投票标记

**结果录入与结算模式（Story 3.4）：**
- **Result settlement 模式**：`result_service.submit_results()` 同时处理两种流程：`locked → settled`（首次结算）和 `settled → settled`（重新结算）。重新结算时先清空所有 `vote.points = NULL`，再重新计算。整个操作在同一事务中，`db.flush()` 确保原子性。
- **Vote.points 字段**：积分直接存储在 `Vote.points`（nullable int）。结算前为 NULL，结算后为实际积分值。排行榜查询使用 `SELECT user_id, SUM(points) FROM votes WHERE points IS NOT NULL GROUP BY user_id`。此设计避免创建独立积分表。
- **RaceHorse.position 语义**：`NULL` = 未排位（比赛未结算）、`0` = DNF/退赛、`>0` = 实际名次（1=冠军）。此三方语义在结算是更新，在比赛编辑时保持不变。
- **DNF 处理模式**：position=0 的马匹不参与 active_horses 计数，投票给 DNF 马匹的用户得 0 分。active_count 仅统计 `position > 0` 的马匹数量，传递给 scoring_engine 作为 `total_horses` 参数。
- **结果结算 API 模式**：`PUT /api/v1/races/{race_id}/results` 管理员专用端点，接收 `ResultEntry { positions: ResultPosition[] }`。位置校验由 schema 层执行：无重复正数位置、无负数位置、位置从 1 开始连续（无间隔）、所有 race_horse_id 均被覆盖。服务层额外校验比赛状态（拒绝 VOTING 状态的比赛）。
- **useDragSort composable 模式**：`useDragSort.ts` 管理两个响应式列表（activeList + dnfList）。提供 `startDrag`/`commitReorder`/`moveToDnf`/`moveToActive`/`endDrag` 接口。**核心规则：dragover 时只做 preventDefault 不修改列表**（避免 DOM 重排导致浏览器丢失拖拽上下文），列表修改统一在 drop 事件中执行。`commitReorder(fromIndex, toIndex)` 在 activeList 内重排，`moveToDnf(index)` 从 active 移至 dnf，`moveToActive(index)` 从 dnf 移至 active。**CRITICAL：存储 composable 实例时的响应式陷阱**——必须使用 `shallowRef`（非普通 `let`）。普通 `let` 变量变化时 Vue 的 computed 不会重新求值。正确写法：`const resultDragSort = shallowRef<ReturnType<typeof useDragSort> | null>(null)`，所有访问加 `.value`。
- **useDragAutoScroll composable 模式**：`useDragAutoScroll.ts` 提供拖拽时视口边缘自动滚动能力。接收 `enabled`（Ref<boolean>）+ `clientY`（Ref<number>），返回 `autoScrollDirection: Ref<'up' | 'down' | null>`。当 `clientY` 在视口上/下 1/5 区域时自动滚动，速度与距边缘距离成二次幂比。使用 `requestAnimationFrame` 驱动 60fps 平滑滚动。桌面端通过内部 `document.addEventListener('dragover')` 全局捕获鼠标位置；移动端通过父组件 `@touchmove` 传入 `clientY`。**移动端速度补偿**：2.5x 速度系数。`.scroll-container` 作为 `position: fixed; overflow-y: auto` 滚动容器。`reduced-motion` 下箭头动画禁用。已集成到 RaceDetailPage 的全部拖拽上下文（桌面 HTML5 DnD + 移动端 jiggle/长按触控）。
- **移动端抖动编辑模式（RaceDetailPage，替代旧的 300ms 长按拖拽）**：
  - `isJiggleMode` ref 控制全局编辑状态。移动端「编辑」按钮（`.mobile-only`）从标题栏移至 admin 操作栏，与锁定/删除比赛按钮共置同一行；桌面端仍通过拖拽直接编辑。
  - 激活时：`HorseDetailCard` 添加 `.is-jiggling` class → `@keyframes jiggle` 动画及 `touch-action: none` + `overflow: visible` **仅移动端（`<768px`）生效**（±0.8deg 旋转 + ±1px 位移，0.3s alternate，防止滚动并允许赛前编辑时 ✕ 按钮溢出）；桌面端保持 `overflow: hidden` 且不播放抖动动画。
  - 闸位拖拽：`handleGateTouchStart` 即时激活（无延迟），`handleGateTouchMove` 实时重排，`handleGateTouchEnd` 自动提交 `updateGateOrder`。
  - 结果排名拖拽：`handleResultTouchStart/Move/End/Cancel` 管理 active/DNF 双列表的触控交互；事件绑定与 gate 模式保持一致（handler 内部守卫，不在模板层动态切换）。DNF 卡片松手至 active 区域自动移回。`.result-drag-item` 与 `.gate-drag-item` 一致采用 `width: 100%` 块级容器，配合 `.horse-detail-card` 的 `width: 100%` 保持所有马匹卡片等宽对齐。
  - 进入结果模式：`enterResultMode()` 自动将 `isJiggleMode` 置为 `true`，无需再点编辑按钮。**进入时必须完全重置拖拽状态**：`resultDragOverIndex`、`resultTouchIndex`、`resultDragSource` 全部归位。使用 `resultEntryVersion` ref 计数器递增作为容器 `:key`，强制 Vue 完全销毁并重建整个排名区域子树，确保 `HorseDetailCard` 组件每次都是全新挂载（避免跨 `v-if`/`v-else` 分支的 DOM 复用导致 `onMounted` 不触发）。`handleConfirmResult` 成功后必须**先调用 `exitResultMode()` + `await nextTick()` 完成视图切换，再 `race.value = await getRace(raceId)`** 刷新数据——否则在 ranking 模式下更新 `race.value` 会触发 `gateDragSort` computed 重建 `useDragSort` 实例，造成渲染时序混乱。
  - ✕ 删除按钮（`.delete-card-btn.mobile-only`）：`position: absolute; top: -12px; right: -12px` 相对于 `.horse-detail-card` 根元素定位（`z-index: 2` 确保在投票徽章之上），点击弹出 `ConfirmDeleteModal` 确认后调用 `removeRaceHorse`。**仅在赛前 `voting` 状态的移动端 jiggle 模式下显示**（`show-delete-button="isJiggleMode && isRaceVoting"`，且桌面端 `>=768px` 隐藏，桌面端赛前使用卡片右侧 `.icon-btn-danger.desktop-only` 与底部 `.delete-zone`）；比赛锁定/结算后的赛后排名模式（`resultMode === 'ranking'`）不可移除马匹，严禁渲染删除按钮，退赛/弃权马匹统一拖入 `DNF/弃权区`。
  - 退出时重置所有拖拽状态（`gateTouchIndex`, `gateDragOverIndex`, `resultTouchIndex` 等）；比赛锁定、退出结果模式、组件卸载时自动退出。
  - 桌面端删除区（`.delete-zone`）在移动端通过 `@media (max-width: 767px) { display: none }` 完全隐藏，避免混淆。
  - `prefers-reduced-motion: reduce` 时抖动动画禁用（`animation: none`）。
- **位置连续校验模式**：`ResultEntry.validate_positions()` 在 schema 层校验 `sorted(positive_positions) == list(range(1, len(positive_positions) + 1))`，确保名次无间隔。此校验防止管理员提交 1,3,4,5 等不连续位置导致评分引擎计算错误。

**排行榜模式（Story 3.5）：**
- **Leaderboard 聚合查询模式**：`leaderboard_service.get_leaderboard()` 直接按 `user_id` 聚合非管理员且已具名用户（`User.is_admin == False, User.username.isnot(None)`）的已公开已结算在线投票积分（`votes` JOIN `races` 且 `Race.status == SETTLED, Race.is_hidden == False`）与历史成绩（`historical_scores`），隐藏比赛（`is_hidden=True`）不计入排行榜积分、参与场数、60%门槛分母（`get_matching_races`）及 Head to Head；取消隐藏后已结算积分立即生效。0分计入参与场数，未参与用户返回0。`sort_by` 支持 `total_points`（默认，总分降序再场均）和 `avg_points`（场均降序再总分）。场均模式仅保留参赛次数达到当前筛选有效比赛数60%的选手（`(N*3+4)//5` 向上取整），N复用 `get_matching_races` 的比赛口径，包含0分，不计隐藏比赛或无成绩/仅管理员成绩的赛事；总分模式不套用门槛。页面小字显示筛选比赛数和所需参与场数，全部被排除时显示门槛空态。排序使用 `Fraction(total_points, races_participated)` 精确比值；接口场均保留3位小数，前端 `toFixed(3)` 补足尾零。SQL 均值使用 `ROUND(CAST(sum / divisor AS NUMERIC), 3)`，PostgreSQL 必须显式转为 `Numeric`。排行榜按当前排序指标计算距榜首/上一名差值，场均模式差值同样显示3位小数；`appliedSort` 与成功响应绑定，避免异步请求导致指标与行顺序不一致。
- **Leaderboard 筛选子查询模式**：支持按 6 个 tag 筛选（age_range/sex_restriction/race_grade/country/surface 为多选），以及 date、distance、horse_count 范围筛选。**CRITICAL**：筛选条件**不能**放在 `Vote LEFT JOIN Race` 的 ON 子句中——LEFT JOIN 保留所有 Vote 行，不匹配的 Race 导致 Race 列为 NULL 但 Vote.points 仍参与 SUM。正确做法：在线投票统一通过 `Vote INNER JOIN Race WHERE Vote.points IS NOT NULL AND Race.status = 'settled' AND Race.is_hidden = false`（再叠加可选 `{filters}`）聚合，未命中筛选的用户仍以 0 分显示。
- **Leaderboard 公开端点模式**：`GET /api/v1/leaderboard`、`/leaderboard/races`、`/leaderboard/participants`、`/leaderboard/head-to-head` 均为无认证依赖公开端点（仅纳入 `is_hidden=False` 的在线已结算比赛与历史比赛），路由前缀 `/api/v1`。前端 `apiClient.get('/leaderboard')` 因 baseURL 为 `/api/v1` 正确匹配。
- **排行榜排序菜单**：`LeaderboardSortSelect.vue` 使用 `defineModel<LeaderboardSort>`，选择改变后发出 `change`。使用页面内自定义 listbox（白底、圆角、阴影、绿色选中项及勾选图标），不再使用原生 `<select>` 展开菜单。支持方向键/Home/End 导航、Enter/空格确认、Esc/Tab/点击外部/焦点离开关闭；触发器保持焦点，使用 `aria-activedescendant` 标记活动选项。
- **LeaderboardRow 组件模式**：`LeaderboardRow.vue` 使用原生 `<tr>`/`<td>`，接收 `entry`, `rank`, `isCurrentUser`, `leaderGap`, `previousGap` props。排行榜从第 1 名开始统一使用表格，不再展示前三名领奖台或金色特殊名次；榜首的“距上一名”为 0。保留当前用户高亮、`UserAvatar` QQ 头像（移动端缩小为 22px）及负分红色。包裹带 `.ui-stagger`（`rise-in` `translateY`）行动画的横向滚动表格容器（如 `.table-card`）必须显式加 `overflow-y: hidden`（因单独设 `overflow-x: auto` 会使 `overflow-y` 计算为 `auto`，尾行入场下移会短暂撑出纵向滚动条）。
- **Head to Head**：排行榜使用 `HeadToHeadComparison.vue` + `useHeadToHead.ts`，选择至少两位不同用户，沿用 `appliedFilters`；`/api/v1/leaderboard/participants` 返回所有具名非管理员用户（`user:{user.id}`），`/api/v1/leaderboard/head-to-head` 用 repeated `participant_id` 参数，直接按 `user_id` 查询已公开（`is_hidden=False`）的在线已结算投票与 `historical_scores` 的共同比赛逐场得分。0 分/负分计入交集，隐藏比赛不纳入对比。组件用请求序号和卸载保护阻止旧查询覆盖新结果。
- **历史成绩管理**：管理员入口 `/admin/historical-scores`（管理菜单和排行榜均有链接）。Excel 先调用 `/api/v1/admin/historical-scores/preview` 预览，再携带 `preview_token` 确认导入；预览不写库，数据变化返回 409。导入时场地以 `障碍` 开头统一为 `障碍`，所有障碍赛及非 `G1`/`G2`/`JPN1`/`自定义` 等级（如 `J·G1`、`G3`、`JPN2`）统一归入 `其他`。`historical_scores` 通过 `user_id`（`FK -> users.id ON DELETE CASCADE`，`UNIQUE(race_id, user_id)`）关联 `users`，不再冗余存储 `qq` 和 `display_name`。`historical_import_batches` 仅保留有效批次（无 `undone_at` 列），撤销批次（`undo_batch`）在恢复快照或删除本批次新增比赛后**直接物理删除**该批次记录（`historical_import_changes.batch_id` 经 `ON DELETE CASCADE` 级联删除，`historical_races.import_batch_id` 为 `ON DELETE SET NULL`）。历史成绩修正携带 `expected_points` 防止覆盖并发修改。导入参数 `skip_identical`/`skip_empty` 默认均为 true；0分算有效成绩，0条成绩默认跳过。差异逐场选择 `keep`/`replace`，`historical_import_changes` 的 `before`/`after` 快照 `scores` 仅存 `[{'qq': qq, 'points': points}]`（不含 `display_name`），存在后续有效导入或人工修分冲突时阻止撤销。
- **LeaderboardPage 模式**：`LeaderboardPage.vue` 使用 PageState 枚举（loading/empty/error/success）。success 态渲染原生 `<table>`（`<thead>`+`<th scope="col">`+`<tbody>`+`LeaderboardRow` as `<tr>`）。useDragSort composable 外的结构化表格数据优先使用原生 `<table>` 保证列对齐（与 DashboardPage、HorsesPage 一致）。empty 态条件：`data.length === 0 || data.every(e => e.races_participated === 0)`。
- **LeaderboardPage 筛选交互模式**：多选标签和数字范围输入修改后**不立即触发 API**——用户选完所有条件后点击绿色实心"应用筛选"按钮一次性提交。"清除筛选"按钮立即生效。`v-model.number` 清空后产生空字符串 `""` → 使用 `toNum()` 辅助函数（`typeof v === 'number' && !isNaN(v) ? v : undefined`）过滤为非数字值。`hasActiveFilters()` 必须检查所有 7 个筛选维度（6 个 tag 数组 + 4 个数字范围），确保 surface 等维度不遗漏。
- **排行榜排除 admin 模式**：`leaderboard_service.get_leaderboard()` 查询中添加 `.where(User.is_admin == False)` 过滤 admin 用户。admin 不能投票，无有效积分，不应出现在排行榜中。
- **review 通过后的 story 状态转换**：code-review 发现被全部修复后，story 状态从 `review` → `done`。同时 sprint-status.yaml 同步更新。此流程在 code-review 工作流的 Step 6 中自动执行。
- **catch 规范**：所有 `catch` 块必须使用 `catch (err)`（非裸 `catch`），以便区分错误类型。即使在仅设置 error 状态的简单场景中也需遵守此规范。

**历史 QQ 占位用户与一个 QQ 一个账户：**
- `users.qq` 受全局唯一索引 `ix_users_qq` 约束（严格一个 QQ 一行 `User`）。
- 历史成绩导入（`import_workbook`）写入成绩前先调用 `placeholder_user_service.ensure_placeholders()`：
  - 若该 QQ 在 `users` 中尚无记录：新建占位 `User(username=<去重后表格名>, password_hash=None, qq=qq, invite_code=<8位随机码>, is_admin=False)`；
  - 若该 QQ 已存在未设用户名/密码的待注册邀请码行（`username is None, password_hash is None`）：原地填充去重后的 `username` 升级为占位用户并复用其 `invite_code`；
  - 若已有正式用户或占位用户：直接复用其 `user.id` 写入 `historical_scores.user_id`。
- 占位身份由 `is_placeholder(user)` 判断：`not user.is_admin and user.password_hash is None and user.username is not None`（不再使用 `!placeholder:` 密码前缀）。`security.verify_password()` 对 `password_hash is None` 直接返回 `False`。
- 撤销导入或导入替换后调用 `remove_orphan_placeholders()`：使用 `with_for_update()` 锁定已无任何 `HistoricalScore` 的占位用户行，将其 `username` 置回 `None`（退化为普通待注册邀请码行，保留原 `id`、`qq`、`invite_code` 供后续注册或再次导入复用，避免并发注册被误删）。
- **占位用户受保护**：`GET /api/v1/admin/invite-codes` 直接查询 `users` 表返回 `placeholder_username`；管理页显示“占位·待注册”和“不可删除”。后端删除占位用户的邀请码返回 409 `PLACEHOLDER_PROTECTED`。
- `create_invite_code`：QQ 已有正式账户（或管理员）返回 409 `QQ_ALREADY_REGISTERED`；已有未激活邀请码返回 409 `QQ_HAS_UNUSED_CODE` 并提示保留的码；若存在缺失邀请码的未激活行则原地补发。
- 删除已使用的邀请码会删除对应 `User` 行并级联删除投票与历史成绩；空的历史比赛保留。若之后撤销涉及这些比赛的“更新”批次，会因快照不一致返回 `UNDO_CONFLICT`。
- QQ 格式统一为 5–20 位 ASCII 数字（`app/utils/qq.py` 的 `is_valid_qq`，不用 `str.isdigit()`，避免全角数字）：注册、QQ 登录、生成邀请码和历史导入都校验；前端注册/登录/生成邀请码使用 `/^[0-9]{5,20}$/`。

**QQ 头像（后端代理）：**
- `avatar_key` 使用带 `v1_` 前缀的 URL 安全 AES-SIV 密文。服务端从 `jwt_secret` 派生独立密钥，公开号码标识保持稳定且不暴露原始 QQ。`LeaderboardEntry`、Head to Head 参与者、`VoteListEntry`、`UserInfo`（登录/注册/重置密码）均带 `avatar_key`。
- `GET /api/v1/avatars/{avatar_key}`（公开）：先验证密文，再通过 `users.qq` 唯一索引检查 QQ 是否存在（所有历史成绩关联用户均在 `users` 表中）；请求上游之前关闭查询会话。服务端复用模块级 `httpx.AsyncClient` 下载头像，并合并同一 QQ 的在途请求。仅接受 `image/*` 且 ≤512KB。成功缓存 3 天，非图片/4xx 缓存 1 分钟，超时/连接异常/5xx 可立即重试。响应 `Cache-Control` 跟随 `avatar_cache_seconds`；未知 key 或下载失败返回 404 `AVATAR_NOT_FOUND`。已保存旧版头像 key 的会话重新登录后会得到新版 key。
- 测试中通过 monkeypatch `avatar_service.download` 模拟上游，并在每例前后 `clear_cache()`；**不得**在测试中访问真实网络。
- 前端统一用 `components/UserAvatar.vue`（props：`avatarKey`、`name`、`size`）：有 key 时加载 `/api/v1/avatars/{key}`，无 key 或图片 `error` 时回退为首字母；key 变化会重试。父组件用 class 覆盖颜色/尺寸时选择器需比 `.user-avatar` 更具体（如 `.user-chip .avatar`、`.name-cell .row-avatar`）。已用于顶栏当前用户、排行榜行、Head to Head 选择列表/已选标签/表头、投票分布投票人名单。旧 localStorage 会话没有 `avatar_key`，重新登录后才显示头像。

**隐藏比赛模式：**
- **Race 模型 `is_hidden` 列**：ORM 与数据库层统一默认 `True`（`server_default=sa.true()`，新创建比赛默认隐藏），布尔类型。结算时仍正常写入 `Vote.points`，但 `is_hidden=True` 的比赛不计入排行榜积分统计、筛选比赛列表、60%场均门槛与 Head to Head；切换为公开（`is_hidden=False`）后立即计入排行榜。
- **Service 层 `include_hidden` 参数模式**：`get_races()` 和 `get_race()` 新增 `include_hidden: bool = False` 参数。调用方（端点层）根据当前用户是否为管理员传递该参数。非管理员且 `include_hidden=False` 时，`is_hidden=True` 的比赛从查询结果中排除。
- **端点 `PATCH /{race_id}/toggle-hidden`**：管理员专用端点，切换 `is_hidden` 标志。Service 层 `toggle_race_hidden()` 执行 `race.is_hidden = not race.is_hidden` 后 `flush()` + `refresh()`。
- **错误码模式**：非管理员访问隐藏比赛详情时返回 `404` 但错误码为 `RACE_HIDDEN`（区别于通用的 `NOT_FOUND`），便于前端显示"当前比赛已隐藏"。
- **前端客户端过滤模式**：`HomePage.vue` 使用 `visibleRaces` 计算属性在客户端过滤隐藏比赛：`authStore.isAdmin` 时显示全部，否则过滤 `is_hidden=true` 的比赛。此模式确保退出登录时隐藏比赛立即消失（无需重新请求）。
- **前端眼睛按钮模式**：管理员在每个比赛卡片和详情页标题栏看到眼睛 SVG 按钮，点击切换隐藏状态。隐藏状态下按钮为红色边框+横线眼睛图标，卡片半透明显示。使用 `@click.stop` 阻止卡片点击冒泡。

**已结算结果展示模式（Story 3.6）：**
- **horse_votes 端点扩展模式**：`GET /api/v1/races/{race_id}` 在已结算状态下扩展返回 `horse_votes` 字段：`{"horses": [{"race_horse_id": id, "horse_id": id, "snapshot_data": {...}, "position": 1, "votes": [{"username": "user", "points": 10}]}]}`。条件判断使用 `race.status == RaceStatus.SETTLED`（枚举比较，非字符串比较）。空列表判断使用 `is not None` 而非布尔真假（避免空列表 `[]` 被当作 falsy）。
- **get_race_results_grouped_by_horse 查询模式**：`vote_service.get_race_results_grouped_by_horse()` 使用 `select(RaceHorse).options(selectinload(RaceHorse.votes).selectinload(Vote.user))` 按马匹分组加载投票。排序：`case((position==0, 2), (is_(None), 3), else_=1)` 将正常马匹排前、DNF 排中、NULL 排后，再按 `position.asc().nulls_last()` 排序。
- **积分颜色编码模式**：正分 `--color-primary`（绿色）、负分 `--color-destructive`（红色）、零分 `--color-ink-disabled`（灰色）。所有分值使用 Barlow Condensed 14px bold（`var(--font-display)` + `var(--text-body-sm)`）。DNF 马匹投票固定显示 `0`（灰色），忽略实际 `vote.points` 值。
- **名次标签模式**：1st/2nd/3rd 金色底 `--color-accent` 白字、4th+ 灰底 `--color-ink-disabled` 白字、DNF 灰底斜体。aria-label 使用中文序数（"第一名"/"第二名"/"弃权"）。DNF 整个 wrapper 为 `opacity: 0.5`，但 `.no-votes` 文字覆盖为 `opacity: 1` 保持可读。
- **已结算比赛管理员按钮模式**：比赛详情页中 `v-if="isRaceSettled && authStore.isAdmin"` 渲染 "修改结果" 按钮（透明背景 + 竞马绿 1px 边框 + 绿色文字），hover 时反转（绿底白字）。链接到 `/admin/races/${raceId}/results`。使用 `router.push()` SPA 跳转。

**比赛详情页删除比赛模式：**
- **删除按钮位置**：比赛详情页底部 admin 操作区（`v-if="isAdmin && !isRaceSettled && resultMode === 'idle'"`），用分隔线与上方操作按钮区分。红色主题样式（`--color-destructive`），hover 反转红底白字。已结算比赛不显示。
- **删除流程**：点击删除按钮 → 弹出 `ConfirmDeleteModal` 确认弹窗（显示比赛名称）→ 确认后调用 `deleteRace()` API → 成功后 `router.push('/')` 跳转回首页。错误信息显示在按钮下方。

**结算重算与前走更新模式（已移除审计日志表）：**
- 已移除 `score_change_logs` 表、`horse_auto_update_logs` 表及 `GET /api/v1/races/{race_id}/results/history` 端点。
- **结果重算模式**：`result_service.submit_results()` 在 `race.status == RaceStatus.SETTLED` 重算时，先将所有 `vote.points = None` 清空，再按新名次重算积分并在同一事务 `flush()` 内原子提交。
- **结算自动更新前走模式**：`result_service.submit_results()` 在同一事务中遍历 `race.race_horses`，按 `race.date >= prev_date` 条件直接原地更新 `Horse` 表的 `previous_result`、`previous_result_date`、`previous_result_position`。

---

**马匹年龄动态计算模式（Story 4.x）：**
- Horse 模型不存储整数 `age`，改为存储 `birth_year`（出生年，如 2022）+ `hemisphere`（"north"/"south"）。
- 前端 `HorseDetailCard.vue` 提供 `computeAge(birthYear, hemisphere, onDate)` 函数动态计算年龄：
  - 北半球：1月1日起 `今年-出生年` 岁
  - 南半球：8月1日起 `今年-出生年` 岁
- 卡片接收 `birthYear`/`hemisphere`/`referenceDate` props（可选，不传则用当天日期）。
- 比赛页面向 `HorseDetailCard` 传入 `race.date` 作为 `referenceDate`，确保显示比赛中实际年龄。
- `RaceHorse.snapshot_data` 中 `age` 字段已被 `birth_year` 完全替代；前端不再兼容读取 `age`，所有快照统一使用 `birth_year`。

**出生国/所属地 新增选择与半球一致性模式（Story 4.x）：**
- 出生国（`origin`）与半球（`hemisphere`）强制保持同国唯一一致：后端 `create_horse()` / `update_horse()` 自动去除 `origin`、`location` 首尾空白；未设置 `origin` 时禁止单独设置 `hemisphere`（400 `ORIGIN_REQUIRED_FOR_HEMISPHERE`）；已有出生国若已绑定半球，未传 `hemisphere` 时自动继承、传入冲突半球时拒绝（409 `ORIGIN_HEMISPHERE_CONFLICT`）；首次为已有无半球记录的出生国指定半球时自动回填同国记录。
- PostgreSQL 使用事务级 advisory lock 串行化出生国半球相关的马匹写入和删除，覆盖该国尚无马匹时的首次绑定。
- 统计、写入校验和切换共用出生国非空半球的 `DISTINCT` 查询。`get_origins_stats()` 在同一条 SQL 中关联各国马匹总数，半球为空的马匹也计入总数。
- `POST /api/v1/horses/origins/{origin}/toggle-hemisphere` 端点将该出生国下**所有**马匹统一更新为同一目标半球（不存在该出生国返回 404，尚未绑定半球返回 409 `ORIGIN_HEMISPHERE_UNSET`），前端切换成功后同步更新列表中的全部同国马匹。
- 出生国（`origin`）下拉使用原生 `<select>`，包含 "+ 新增国家"，选中后切换为文本输入模式；若输入的国家名已存在于 `sortedCountries` 且所选半球与既有绑定冲突，前端直接拦截提示。编辑马匹切换 `origin` 时须一并携带对应的 `hemisphere`。新增国家确认时先将半球留在表单中，保存成功后才从统计刷新页面的国家半球映射。
- 所属地（`location`）与出生国完全独立，逻辑相同但没有半球信息。新增确认后不立即修改 `sortedCountries`/`sortedLocations`，而是显示临时选项，保存后通过 `refreshCountryList()` 刷新。

**UI 动效与共享原语（frontend lively-ui 重构）：**
- 设计令牌（`variables.css`）新增：tint 色（`--color-primary-tint` / `--color-accent-tint` / `--color-destructive-tint` 等，替代散落的 `#F0F7F2`、`#FFFDF0`、`#FFF5F5`）、渐变（`--gradient-brand` / `--gradient-gold` / `--gradient-silver` / `--gradient-bronze`）、`--shadow-lg` / `--shadow-xl` / `--shadow-glow-gold`、`--rounded-xl`，以及动效令牌 `--ease-out` / `--ease-spring` / `--ease-in-out`、`--duration-fast|base|slow`、`--stagger-step`。新代码优先用令牌，不要再写裸色值。
- 共享关键帧集中在 `base.css`：`rise-in`、`fade-in`、`pop-in`、`dialog-in`、`shake-x`、`pulse-ring`、`spin`（加上原有 `skeleton-shimmer`）。组件内不要重复定义同名动画。
- `assets/styles/ui.css` 提供 **`ui-` 前缀**的全局原语：`ui-btn`（`--primary` / `--gold` / `--ghost` / `--outline` / `--danger` / `--danger-solid` / `--sm` / `--block`）、`ui-spinner`、`ui-page-header` + `ui-page-eyebrow` + `ui-page-title` + `ui-page-subtitle`、`ui-field` / `ui-label` / `ui-input` / `ui-field-error`、`ui-banner--error|success`（错误横幅自带抖动）、`ui-chip`、`ui-skeleton`、`ui-state`（空/错误态，含 `ui-state-icon` / `ui-state-text`）、弹窗入场 `ui-anim-overlay` + `ui-anim-dialog`、过渡名 `ui-fade` / `ui-collapse`。前缀是为了不和管理页里仍然 scoped 的 `.btn` / `.form-field` 冲突。
- **列表逐项入场**：给条目加 `.ui-stagger` + `:style="{ '--i': index }"`，但 class 只能在首次出现时挂上——用 `useRevealOnce()` 的 `revealing` 控制（`reveal(count)` 后自动在动画结束时撤掉）。原因：CSS 动画在节点被重新插入时会重播，常驻 class 会让拖拽排序（DOM 移动）时卡片反复闪入。
- `useCountUp(source, duration)` / `CountUpNumber.vue`：数字缓动递增，`prefers-reduced-motion` 时直接跳到终值。
- `base.css` 的 reduced-motion 全局规则同时把 `animation-delay` / `transition-delay` 置 0，避免逐项入场在关闭动效时仍有延迟空白。
- 复用组件：`RaceTags.vue`（6 个标签 chip；G1 金、G2 银、JPN1 青、自定义紫，场地带色点；`on-dark` 用于详情页深色横幅）、`HiddenToggleButton.vue`（管理员眼睛按钮，内部 `@click.stop`）、`BrandMark.vue`（金色马蹄铁 logo，渐变 id 用 `useId()` 保证每个实例唯一）、`AuthShell.vue`（登录/注册/重置密码共用外壳，表单控件用 `ui-*`）、`InviteCodeInput.vue`（登录/注册/重置密码共用的 8 格手机验证码式邀请码输入组件，`defineModel<string>`，使用等宽字体 `--font-mono`，支持逐格自动跳焦、Backspace 回删、单格覆盖、任意格粘贴 8 位码与 IME 合成保护）。用户管理页（`InviteCodeTable.vue`）的邀请码展示（`.code-text`、`.created-code`）同样统一使用 `--font-mono` 等宽字体。
- 选项常量统一在 `src/constants/raceOptions.ts`（`AGE_RANGE_OPTIONS` 等），首页创建弹窗与排行榜筛选共用，新增选项只改这一处。
- 比赛详情页顶部为品牌色横幅（`.race-hero`，按状态切换配色），`RaceHeaderEditor` 的标题与 ✎ 按钮颜色为 `inherit` 以适配深色背景。
- `HorseDetailCard.vue` 新增可选 `fieldSize` prop：传入出走头数时右侧闸位块按 **JRA 枠番配色**（`utils/gateBracket.ts`，≤8 头一马一枠，9–18 头按外枠优先补位）。详情页只对 `country === '日本'` 的比赛传入。左侧名次块 1/2/3 名为金/银/铜渐变。
- `HorseDetailCard.vue` 模板是双根（卡片 + Teleport），因此 `inheritAttrs: false` 并在卡片根上 `v-bind="$attrs"`；父组件传入的 class（如 `voted-horse-locked`）的样式写在 HorseDetailCard 自己的 scoped CSS 里（父组件 scoped 选择器匹配不到多根组件的元素）。
- 首页：状态分段筛选（全部/投票中/已锁定/已结算，纯前端过滤 `visibleRaces`），比赛卡片左侧日历块 + 状态色条，悬停上浮；卡片外层 `role="link"` + `tabindex="0"` + Enter 跳转。
- 移动端底部导航高度包含 `env(safe-area-inset-bottom)`，`.scroll-container` 的 `bottom` 也同步加上，避免 iPhone 上导航内容被压扁。

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Update this file if new patterns emerge

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

Last Updated: 2026-11-10 (origin-hemisphere consistency enforcement, single-query origins stats, and uniform hemisphere toggle)
