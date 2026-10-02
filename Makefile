.PHONY: up down logs ban13 ban test eval eval-strict

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api ui

ban13:
	docker compose run --rm ban-loader --departments 13

# Usage: make ban DEPS="13 75 69"
ban:
	docker compose run --rm ban-loader --departments $(DEPS)

test:
	python -m unittest discover -s tests -v

eval:
	python scripts/evaluate_fictional_cases.py --show-success

eval-strict:
	python scripts/evaluate_fictional_cases.py --strict --show-success
