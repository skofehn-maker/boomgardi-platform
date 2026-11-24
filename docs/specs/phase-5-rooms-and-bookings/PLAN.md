# Phase 5 — PLAN

1. `tests/test_rooms_and_bookings.py` — red first: room guards/idempotency,
   public detail read, booking guards, overlap `409`, adjacent-stay success,
   both templates' markup.
2. Models: `app/models/booking.py` (`Booking`, `BOOKING_STATUSES`); `Room`
   gains `idempotency_key` + `UniqueConstraint(listing_id, idempotency_key)`.
3. Schemas: `RoomCreate` already exists; add `BookingCreate` / `BookingResponse`.
4. API: `POST /listings/{id}/rooms` (owner, key), `GET /listings/{id}`
   (published only), new `app/api/v1/bookings.py` with `POST ""`.
5. Routing: mount the bookings router at `/api/v1/bookings`; add the page route
   `GET /listings/{listing_id}` in `app/main.py`.
6. Templates: `listing_detail.html` (new), homepage card → link +
   "مشاهده و رزرو", host dashboard rooms list + افزودن اتاق form.
7. `create_db.py`: import `Booking` so `bookings` is created.
8. Recreate `dev.db`'s empty `rooms` table for the new column, then
   `python create_db.py`; run pytest + compileall.
9. Verify in the browser: add a room, open a listing, book dates, repeat to see
   the overlap refusal.
10. Commit and push `dev`.

`Date` columns for the stay, `DateTime` (UTC) for `created_at` — see ADR 0005.
