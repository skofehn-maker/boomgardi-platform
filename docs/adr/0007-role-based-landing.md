# ADR 0007 — Role-based landing is a client-side policy

- **Status:** accepted
- **Date:** 2026-11-24
- **Phase:** 7

## Context

After login every account landed on `/profile`, so hosts saw a guest profile and
had to find `/host` themselves. The API already knows the role; the frontend had
to guess it from the JWT claim or the cached `current_user` object, and the
profile page mapped everything that was not `admin` to «کاربر مهمان».

## Decision

1. `POST /api/v1/auth/login` returns `role` at the top level of the token
   envelope (`access_token`, `token_type`, `expires_in`, `role`, `user`). The
   nested `user` stays for the pages that already read it.
2. `login.html` owns a single `ROLE_HOME` map (`admin → /admin`,
   `host → /host`, `guest → /profile`, fallback `/profile`) used by both the
   "already signed in" bootstrap and the submit handler. The role is read from
   the response first, then `user.role`, then the JWT claim.
3. Rendering labels come from a role map (`ROLE_LABELS`) instead of a ternary,
   so new roles cannot silently be labelled as guests.
4. Pages stay client-guarded: the API is the authority (every endpoint
   re-checks ownership and role), the browser only decides where to land.

## Consequences

- A host whose token is valid lands on `/host`; an admin on `/admin`.
- `/profile/bookings` and `/profile` keep working for every role, since
  `/api/v1/bookings/mine` returns the caller's bookings regardless of role.
- Roles added later only need a new entry in `ROLE_HOME` / `ROLE_LABELS`; the
  server-side authorization rules remain the real boundary.
