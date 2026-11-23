# Boomgardi Platform - Agent Rules
## Project
Platform for booking eco-lodge accommodations.
Stack: Python 3.11+, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest, Jinja2.
Architecture: Modular Monolith.

## Iron Rules (NEVER violate)
1. No code without SPEC + PLAN + failing test first.
2. Double Booking prevention MUST use PostgreSQL EXCLUDE USING gist. Never application-level logic.
3. All datetimes stored in UTC. Convert to Asia/Tehran only in presentation layer.
4. Every mutating endpoint requires Idempotency-Key header.
5. No secrets in code. Only .env.
6. Every architectural decision -> ADR in docs/adr/.
7. Run pytest before every commit. All tests must pass.

## Database
- Dev/test: SQLite (sqlite+aiosqlite:///./dev.db)
- Production: PostgreSQL (postgresql+asyncpg://...)
- Migrations: Alembic only.

## Response Format for Agent
For every feature request:
1. Write docs/specs/XXX/SPEC.md
2. Write docs/specs/XXX/PLAN.md
3. Write failing tests
4. Write implementation
5. Run tests, show results
Wait for my approval after SPEC+PLAN before writing code.