# Phase 4 — PLAN

1. `tests/test_publish_listing.py` — red first:
   auth/idempotency-key guards, owner happy path, repeat publish, foreign host
   `403`, unknown id `404`, `GET /mine` scoping, host page markup.
2. `app/api/v1/listings.py`:
   - `GET /mine` (current user's listings, both statuses).
   - `PATCH /{listing_id}/publish` (owner-only, idempotency header required,
     `409` for archived), reusing `_load_listing` for the eager `rooms` load.
3. `app/templates/host_dashboard.html`: "اقامتگاه‌های من" card, status chips,
   انتشار button, list loader and PATCH caller; Coffee & Cream hex only.
4. `docs/adr/0004-publish-idempotency-without-a-key-table.md`.
5. `python -m pytest tests -q`, `compileall`, tag/markup sanity check.
6. Run uvicorn, verify `/` and `/host` in the browser.
7. Commit and push `dev`.

No schema change, no migration, no new dependency.
