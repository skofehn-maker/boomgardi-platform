# Phase 7 — PLAN

1. `tests/test_rbac.py` — red first:
   - `role` at the top level of the login response for all three seeded roles;
   - `login.html` carries a role→home map hitting `/admin`, `/host`, `/profile`;
   - `/host` renders the recent-bookings panel wired to `/api/v1/bookings/host`;
   - `/profile` renders the رزروهای من section wired to `/api/v1/bookings/mine`
     and a role-label map, with the old admin-or-guest ternary gone.
2. `TokenResponse.role` + `auth.py` passing `user.role`.
3. `login.html`: shared `ROLE_HOME` map for bootstrap and submit redirects.
4. `host_dashboard.html`: رزروهای اخیر card + loader.
5. `profile.html`: `ROLE_LABELS` map and the bookings section + loader.
6. pytest, compileall, template sanity; browser pass through all three roles.
7. Commit and push `dev`.
