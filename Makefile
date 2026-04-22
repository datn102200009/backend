.PHONY: help install dev prod migrate makemigrations test lint format clean freeze

help:
	@echo "Available commands:"
	@echo "  make install              - Install dependencies"
	@echo "  make dev                  - Run development server"
	@echo "  make prod                 - Run production server"
	@echo "  make migrate              - Run database migrations"
	@echo "  make makemigrations       - Create new migrations"
	@echo "  make test                 - Run tests"
	@echo "  make lint                 - Run linters (flake8, isort)"
	@echo "  make format               - Format code (black, isort)"
	@echo "  make clean                - Clean up temporary files"
	@echo "  make freeze               - Generate requirements.txt"
	@echo "  make shell                - Django shell"
	@echo "  make createsuperuser      - Create admin user"
	@echo "  make docker-build         - Build Docker image"
	@echo "  make docker-up            - Start Docker containers"
	@echo "  make docker-down          - Stop Docker containers"

install:
	pip install -r requirements/dev.txt

dev:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev python manage.py runserver

prod:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.production gunicorn --bind 0.0.0.0:8000 datn_backend.wsgi:application

migrate:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev python manage.py migrate

makemigrations:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev python manage.py makemigrations

test:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev pytest --cov=apps --cov-report=html

lint:
	flake8 datn_backend apps manage.py
	isort --check-only datn_backend apps manage.py

format:
	black datn_backend apps manage.py
	isort datn_backend apps manage.py

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.pytest_cache' -delete
	find . -type d -name '.coverage' -delete
	find . -type d -name 'htmlcov' -delete

freeze:
	pip freeze > requirements/base.txt

shell:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev python manage.py shell

createsuperuser:
	DJANGO_SETTINGS_MODULE=datn_backend.settings.dev python manage.py createsuperuser

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f web
