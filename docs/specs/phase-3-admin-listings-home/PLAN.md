# Phase 3 — PLAN

Order of work (Iron Rule 1: SPEC + PLAN + failing test first).

1. `tests/test_phase3_admin_and_home.py` — red first:
   - admin listings endpoint: 401 anonymous, 403 guest, admin sees drafts and
     published rows with title/city/status.
   - `/admin` page ships the listings view markup.
   - `/` renders the homepage (no redirect) with the theme and no external URLs.
2. `seed_user.py` — data-driven `SEED_USERS` list, upsert by email.
3. `app/api/v1/listings.py` — `GET /admin` guarded by `get_current_admin`.
4. `app/templates/admin.html` — `#view-dashboard` / `#view-listings` switch,
   listings table, status badges, lazy fetch of `/api/v1/listings/admin`.
5. `app/templates/index.html` — Coffee & Cream homepage with the card grid.
6. `app/main.py` — `GET /` renders `index.html`.
7. `python seed_user.py`, `python -m pytest tests -q`, `compileall`.
8. Commit and push to `origin dev`.

No schema change, so no migration is needed. No new dependency.
