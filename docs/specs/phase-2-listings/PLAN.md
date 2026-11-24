# Phase 2 — Implementation Plan

Order of work (test-first, see SPEC acceptance criteria):

1. **Models** — `app/models/listing.py`: `Listing`, `Room`, `LISTING_STATUSES`.
   `create_db.py` imports the module so `Base.metadata` knows the tables.
2. **Schemas** — `app/schemas/listing.py`: `ListingCreate`, `ListingResponse`,
   `RoomCreate`, `RoomResponse` (Pydantic v2, `from_attributes=True`).
3. **Tests** — `tests/test_listings.py`, six cases mirroring the acceptance criteria.
   Run them first: all red (404 for the missing routes).
4. **API** — `app/api/v1/listings.py`
   - `POST ""` → `get_current_user`, `Idempotency-Key` header, replay detection,
     status forced to `draft`, re-select with `populate_existing` so `rooms` is loaded.
   - `GET ""` → `status == "published"`, `created_at.desc()`, `selectin` rooms.
   - `main.py`: `app.include_router(listings_router, prefix="/api/v1/listings")`.
5. **UI** — `app/templates/host_dashboard.html`, Coffee & Cream palette
   (`#f5f0e6`, `#fdfbf7`, `#ffffff`, `#3e2723`, `#6f4e37`, `#4e342e`, `#d7ccc8`),
   internal CSS only, no external links; form posts via `fetch` with the stored JWT
   and a generated `Idempotency-Key`. `main.py`: `GET /host` route.
6. **Verify** — green tests, `python -m compileall -q app tests`,
   `python create_db.py` then inspect the SQLite schema.
7. **Commit & push** — commit the whole phase to `dev`, push `origin dev`.

Risk notes:

- SQLAlchemy async: touching `listing.rooms` outside a `select` raises
  `MissingGreenlet`. Mitigation: `lazy="selectin"` + re-select with
  `populate_existing=True` after commit.
- Cross-database compatibility: UUID PKs are mapped with SQLAlchemy's default UUID
  type, which works on SQLite (dev) and PostgreSQL (prod).
- Removing a host must not orphan listings: FK `ON DELETE CASCADE`.

Rollback: revert the commit; `dev.db` is git-ignored, so re-running `create_db.py`
on the previous revision restores the old schema.
