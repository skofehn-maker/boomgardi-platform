# ADR 0001 — JWT bearer authentication for the Jinja2 frontend

- **Status:** Accepted
- **Date:** 2026-11-24

## Context
The project previously had a password-hashing helper but no working token issuance: the
token function referenced undefined names, the secret was hard-coded, and `/login` did not exist.
The UI is server-rendered Jinja2 with no build step, and the API is consumed both by the pages and
(potentially) by other clients.

## Decision
1. Issue **stateless HS256 JWTs** with `python-jose`, signed with `settings.JWT_SECRET`
   (`JWT_SECRET` in `.env`), 30-minute TTL configurable through `ACCESS_TOKEN_EXPIRE_MINUTES`.
2. Claims: `sub` (user UUID), `email`, `role`, `name`, `iat`, `exp`. `exp`/`iat` are
   timezone-aware UTC.
3. The browser stores the token in `localStorage` and sends `Authorization: Bearer <token>`; the
   FastAPI dependency `get_current_user` validates it on every protected API call.
4. Authorisation lives on the API, not on the HTML routes: `/admin` and `/profile` are public
   shells that redirect client-side when the token is missing, invalid or lacks the role.
5. Role checks are explicit (`get_current_admin`) rather than inferred from the token payload only,
   because the database row is re-read on each request (`is_active`, demotion take effect
   immediately).

## Consequences
- **Positive:** no session store, horizontal scaling friendly, the same token works for future
  mobile/SPA clients.
- **Negative:** no server-side revocation before expiry; a stolen token is valid until `exp`.
  Mitigated later by short TTL + refresh tokens. `localStorage` is XSS-readable, so every dynamic
  value rendered into the DOM must be escaped (enforced in the templates).
- **Alternative rejected:** HttpOnly cookie sessions — would require CSRF handling and would not
  serve non-browser API clients.
