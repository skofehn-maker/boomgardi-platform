# PLAN — Professional UI + Real JWT Authentication

## Step 1 — Specification & ADR
- [x] `docs/specs/ui-upgrade/SPEC.md`
- [x] `docs/adr/0001-jwt-authentication.md` (JWT in `localStorage` + Bearer header decision)

## Step 2 — Tests first (`tests/test_auth_and_users.py`)
Against an in-memory SQLite database with `get_db` overridden, via `httpx.ASGITransport`:
1. `POST /login` with valid credentials → `200`, three-part JWT, `user.role == "admin"`.
2. `POST /login` with a wrong password → `401`, no token in body.
3. `GET /api/v1/users/` without a token → `401`.
4. `GET /api/v1/users/` with an admin token → `200` and the seeded user is present.
5. `GET /api/v1/users/` with a guest token → `403`.

## Step 3 — Backend
1. `app/core/security.py`: settings-driven `create_access_token` / `decode_access_token`,
   UTC-aware expiry, hardened `verify_password`.
2. `app/api/deps.py`: `HTTPBearer` scheme, `get_current_user`, `get_current_admin`.
3. `app/schemas/user.py`: `UserLogin`, `TokenResponse`, UUID/datetime-aware `UserResponse`
   (`model_config = ConfigDict(from_attributes=True)`), password length validation.
4. `app/api/v1/auth.py`: fixed `register` (missing `User` import, `password=` instead of
   `password_hash=`), added `POST /login`.
5. `app/api/v1/users.py`: protected `GET /`.
6. `app/main.py`: routers, static mount, `/`, `/login`, `/admin`, `/profile`.

## Step 4 — Templates
1. `login.html`: gradient + glass card, RTL, fetch-based submit, token storage, role redirect,
   error banner, password visibility toggle.
2. `admin.html`: right sidebar (drawer under `md`), top bar, KPI cards, searchable users table,
   role/status badges, Tehran-formatted dates, skeleton loading + error/empty states.
3. `profile.html`: identity card, stats, account details, sign-out.

## Step 5 — Verification
- `python -m compileall app` (syntax) and `python -m pytest tests -q` (behaviour).
- No server start (per request).

## Risks
- Tailwind CDN requires network access at page load; acceptable for this iteration, flagged for a
  future bundled build if the app must run offline.
- The pages are static shells, so an unauthenticated visitor can see the layout for a moment before
  the API returns `401` and the script redirects to `/login`. No data is exposed.
