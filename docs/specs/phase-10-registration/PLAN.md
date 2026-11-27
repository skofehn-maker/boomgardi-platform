# Phase 10 — Plan

## 1. Failing tests — `tests/test_registration.py`
- `test_register_page_renders_form`: `GET /register` returns 200 with the form
  fields (name, email, password, role select) and a link to `/login`.
- `test_login_page_links_to_register`: `GET /login` contains `/register` and the
  Persian label for the link.
- `test_register_persists_full_name_and_role`: posting `full_name`, `email`,
  `password`, `role="host"` creates the user with those values (guest default too).
- `test_register_rejects_admin_role`: `role="admin"` returns 422.

## 2. Implementation
- `app/schemas/user.py`: `UserCreate` gains `full_name: str | None` and
  `role: Literal["guest", "host"] = "guest"`.
- `app/api/v1/auth.py`: persist `full_name` and `role`, trimming the name.
- `app/main.py`: `GET /register` → `register.html`.
- `app/templates/register.html`: Coffee & Cream card, client-side validation,
  `POST /api/v1/auth/register`, redirect to `/login?registered=1`.
- `app/templates/login.html`: link to `/register`.
- `login.html` shows a success note when `?registered=1` is present.

## 3. Verification
- `python -m pytest` — full suite green before commit.
- `git add . && git commit -m "feat: add registration page" && git push origin dev`.
