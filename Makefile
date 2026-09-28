.PHONY: up down logs ban13 ban test

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
