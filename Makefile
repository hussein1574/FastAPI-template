.PHONY: run build test migrate new-migration clean

# Start all services
run:
	docker-compose up --build

# Build without starting
build:
	docker-compose build

# Run tests locally
test:
	cd Backend && pytest -v

# Run database migrations
migrate:
	docker-compose exec backend alembic upgrade head

# Create a new migration (usage: make new-migration msg="add projects table")
new-migration:
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

# Clean up containers and volumes
clean:
	docker-compose down -v

# Restart backend only
restart:
	docker-compose restart backend

# View backend logs
logs:
	docker-compose logs -f backend

# Generate a new SECRET_KEY
secret-key:
	python -c "import secrets; print(secrets.token_hex(32))"
