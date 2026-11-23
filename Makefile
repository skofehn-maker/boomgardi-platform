install:
	pip install -e .

run:
	uvicorn app.api.v1.main:app --reload

test:
	pytest tests

migrate:
	alembic upgrade head

seed:
	# command to seed the database
