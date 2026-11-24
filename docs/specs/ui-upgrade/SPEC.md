# SPEC — Professional UI + Real JWT Authentication

## Goal
Upgrade the existing FastAPI + Jinja2 proof-of-concept into a presentation layer that looks and
behaves like a modern admin dashboard, without changing the stack (no React/Next, no build step).

## Scope

### 1. Presentation layer (Tailwind CSS via CDN)
| Template | Behaviour |
| --- | --- |
| `app/templates/login.html` | RTL glassmorphism login: gradient background, blurred colour blobs, white card, focus/hover states, inline validation and show/hide password. Submits JSON to `POST /api/v1/auth/login` via `fetch`, stores the token in `localStorage`, then redirects admins to `/admin` and everyone else to `/profile`. |
| `app/templates/admin.html` | Fixed right sidebar (RTL), sticky top navigation bar, main area with KPI cards and a users table loaded from `GET /api/v1/users/`. Sidebar collapses on small screens. |
| `app/templates/profile.html` | User dashboard: identity card, quick stats, account metadata, sign-out. |

Constraints:
- No frontend toolchain. Tailwind Play CDN only, all page logic in inline `<script>`.
- Persian (fa) copy, `dir="rtl"`, Vazirmatn font with system fallbacks.
- All user-supplied strings rendered through an escaping helper (no `innerHTML` interpolation of raw data).
- Mobile first: usable from 360px up; sidebar becomes an overlay drawer below `md`.

### 2. Authentication
- `app/core/security.py`
  - Real JWT via `python-jose` (already a dependency).
  - Secret, algorithm and TTL come from `app.core.config.settings` (`.env`), never hard-coded.
  - `exp`/`iat` are timezone-aware UTC (`datetime.now(timezone.utc)`).
  - `decode_access_token()` raises `JWTError` on tampering/expiry.
  - `verify_password()` returns `False` instead of raising on malformed hashes.
- `POST /api/v1/auth/login` verifies the bcrypt hash and returns
  `{access_token, token_type, expires_in, user}`. Wrong email and wrong password produce the same
  `401` body (no account enumeration). Inactive accounts get `403`.
- Token claims: `sub` (user id), `email`, `role`, `name`, `iat`, `exp`.

### 3. Protected user listing
- `GET /api/v1/users/` — requires `Authorization: Bearer <jwt>`; returns every user ordered by
  newest first. Admin role required (it exposes other accounts).
- Dependencies: `get_current_user` (401), `get_current_admin` (403) in `app/api/deps.py`.

### 4. Routing
`app/main.py` serves `/` (redirect to `/login`), `/login`, `/admin`, `/profile`, mounts `/static`
and includes the auth + users routers under `/api/v1`.

## Out of scope
Booking/lodging domain endpoints, Alembic revisions, server-side sessions or cookies, refresh
tokens, role management UI.

## Non-functional
- Iron rule 3: datetimes stored and transported in UTC; the browser renders them in
  `Asia/Tehran` via `Intl.DateTimeFormat`.
- Iron rule 5: no secrets in source; `JWT_SECRET` is read from `.env`.
- The three HTML pages are public shells; authorisation is enforced on every API call.
