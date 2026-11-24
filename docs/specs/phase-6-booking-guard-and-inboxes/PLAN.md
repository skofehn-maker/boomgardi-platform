# Phase 6 — PLAN

1. `tests/test_bookings_flow.py` — red first: host inbox scoping, confirm/cancel
   guards and transitions, cancelled dates becoming bookable again, guest inbox
   scoping, both new pages, navbar markup, migration content.
2. Alembic scaffolding: `alembic.ini`, `alembic/env.py` (async + offline),
   `alembic/script.py.mako`, `alembic/versions/0001_booking_no_overlap.py`
   (PostgreSQL-only `EXCLUDE USING gist`).
3. Schemas: `HostBookingResponse`, `GuestBookingResponse`.
4. `app/api/v1/bookings.py`: `GET /host`, `GET /mine`, `PATCH /{id}/confirm`,
   `PATCH /{id}/cancel`.
5. `app/main.py`: `GET /host/bookings`, `GET /profile/bookings`.
6. Templates: `host_bookings.html`, `profile_bookings.html`, host-dashboard and
   profile nav links, shared navbar behaviour + logout-to-`/` across
   `index.html`, `listing_detail.html`, `admin.html`, `profile.html`.
7. Verify: `python -m alembic upgrade head --sql` with a PostgreSQL URL prints
   the constraint; `alembic upgrade head` on the SQLite dev DB is a no-op;
   pytest; compileall; browser pass over both inboxes.
8. Commit and push `dev`.
