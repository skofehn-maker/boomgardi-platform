# ADR 0009 — Search/filter and mock payment/cancellation

- Search/filter is implemented as optional query params on the existing public
  `GET /api/v1/listings` endpoint (`city`, `max_price`); no new endpoint.
- Mock payment is a `PATCH /api/v1/bookings/{id}/pay` that transitions
  `pending -> confirmed`; cancellation reuses `PATCH .../cancel` but ownership is
  extended to the booking's guest owner (in addition to the hosting host).
- No schema/model/migration changes; status remains a string column.
- Mutating endpoints keep requiring `Idempotency-Key`.
