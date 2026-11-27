# Phase 12 — PLAN

## Steps

1. `tests/test_profile_edit.py` first (must fail with 404/405):
   - `PUT /api/v1/users/me` without a token → 401.
   - Without `Idempotency-Key` → 422.
   - Renaming only → 200, new name visible through `POST /api/v1/auth/login`.
   - Changing the password only → 200; old password stops working, new one logs in.
   - A 7-character password → 422; `{}` → 422.
   - `GET /profile` contains "ویرایش پروفایل", "ذخیره تغییرات",
     `/api/v1/users/me` and `Idempotency-Key`.
2. `app/schemas/user.py`: add `UserUpdate` (optional `full_name`, `password`)
   with a model validator rejecting an empty payload.
3. `app/api/v1/users.py`: add `PUT /me` using `get_current_user`, hashing the
   new password with `hash_password`, returning `UserResponse`. Declared after
   `GET /`; no path conflict because the methods differ.
4. `app/templates/profile.html`: add the edit card, its CSS and the submit
   handler (JSON PUT with bearer token + `Idempotency-Key`, refresh of the
   cached user, success/error notices).
5. `docs/adr/0010-self-service-profile-update.md` for the idempotency decision.
6. Full `pytest`, then commit and push.

## Iron rules

- Rule 1: this SPEC/PLAN plus the failing test come before the code.
- Rule 3: unchanged — no datetime is accepted or stored here.
- Rule 4: `Idempotency-Key` is a required header on the new endpoint.
- Rule 5: no secret is added; the hash comes from `hash_password`.
- Rule 6: ADR 0010 records the "absolute write, no dedup table" decision.
- Rule 7: full suite runs before the commit.

## Risk

`profile.html` is client-rendered, so the test can only assert the form markup
and the API contract. The rendered form is not exercised by pytest; that gap is
reported, not hidden.
