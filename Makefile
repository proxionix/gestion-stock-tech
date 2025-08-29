# Stock Management System - Makefile
# Enterprise-grade Django application

.PHONY: help build up down restart logs shell migrate superuser test lint format check-security clean

# Default target
help:
	@echo "Stock Management System - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  up          - Start development environment"
	@echo "  down        - Stop all services"
	@echo "  restart     - Restart all services"
	@echo "  build       - Build Docker images"
	@echo "  logs        - View logs (use SERVICE=name for specific service)"
	@echo "  shell       - Open Django shell"
	@echo ""
	@echo "Database:"
	@echo "  migrate     - Run database migrations"
	@echo "  superuser   - Create Django superuser"
	@echo "  seed        - Load seed data"
	@echo ""
	@echo "Development Tools:"
	@echo "  test        - Run tests with coverage"
	@echo "  lint        - Run linting (ruff, mypy)"
	@echo "  format      - Format code (black, ruff)"
	@echo "  check-security - Run security checks"
	@echo ""
	@echo "Deployment:"
	@echo "  prod-up     - Start production environment"
	@echo "  prod-down   - Stop production environment"
	@echo "  backup      - Backup database and media"
	@echo "  restore     - Restore from backup"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean       - Clean up Docker images and volumes"
	@echo "  update-deps - Update Python dependencies"

# Development Commands
up:
	docker-compose up -d
	@echo "Services started. Web app available at http://localhost:8000"
	@echo "API docs available at http://localhost:8000/api/docs/"

down:
	docker-compose down

restart:
	docker-compose restart

build:
	docker-compose build

logs:
ifdef SERVICE
	docker-compose logs -f $(SERVICE)
else
	docker-compose logs -f
endif

shell:
	docker-compose exec web python manage.py shell_plus

# Database Commands
migrate:
	docker-compose exec web python manage.py migrate

superuser:
	docker-compose exec web python manage.py createsuperuser

seed:
	docker-compose exec web python manage.py loaddata fixtures/initial_data.json

# Development Tools
test:
	docker-compose exec web python -m pytest --cov=apps --cov-report=html --cov-report=term-missing

lint:
	docker-compose exec web ruff check apps/ config/
	docker-compose exec web mypy apps/ config/

format:
	docker-compose exec web black apps/ config/
	docker-compose exec web ruff format apps/ config/

check-security:
	docker-compose exec web python manage.py check --deploy
	docker-compose exec web bandit -r apps/ config/

# Production Commands
prod-up:
	COMPOSE_PROFILES=production docker-compose -f docker-compose.yml up -d --build
	@echo "Production services started"

prod-down:
	COMPOSE_PROFILES=production docker-compose -f docker-compose.yml down

# Backup and Restore
backup:
	@echo "Creating backup..."
	docker-compose exec db pg_dump -U stock_user stock_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	tar -czf media_backup_$(shell date +%Y%m%d_%H%M%S).tar.gz media/
	@echo "Backup completed"

restore:
ifndef BACKUP_FILE
	@echo "Usage: make restore BACKUP_FILE=backup_YYYYMMDD_HHMMSS.sql"
else
	docker-compose exec -T db psql -U stock_user -d stock_db < $(BACKUP_FILE)
	@echo "Database restored from $(BACKUP_FILE)"
endif

# Maintenance Commands
clean:
	docker-compose down -v
	docker system prune -a -f
	docker volume prune -f

update-deps:
	docker-compose exec web pip-compile --upgrade requirements.in
	docker-compose build

# Translation Commands
makemessages:
	docker-compose exec web python manage.py makemessages -l fr_BE -l nl_BE -l en

compilemessages:
	docker-compose exec web python manage.py compilemessages

# Quality Assurance
qa: lint test check-security
	@echo "Quality assurance checks completed"

# Setup Commands
setup-dev:
	@echo "Setting up development environment..."
	cp env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run: make up && make migrate && make superuser && make seed"

setup-prod:
	@echo "Setting up production environment..."
	cp env.example .env
	@echo "Please edit .env file for production configuration"
	@echo "Ensure you set strong passwords and proper domains"

# Docker Commands
docker-build:
	docker build -t stock-management:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env stock-management:latest

# Monitoring
monitor:
	docker-compose exec web python manage.py check --deploy
	docker-compose ps
	docker-compose logs --tail=50

# Database Management
db-shell:
	docker-compose exec db psql -U stock_user -d stock_db

db-reset:
	docker-compose down
	docker volume rm stock-project_postgres_data
	docker-compose up -d db
	sleep 10
	make migrate
	make superuser
	make seed

# Static Files
collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

# Celery Management
celery-status:
	docker-compose exec worker celery -A config inspect active

celery-purge:
	docker-compose exec worker celery -A config purge

# SSL Setup (for production)
setup-ssl:
	@echo "Setting up SSL certificates..."
	mkdir -p infra/ssl
	@echo "Place your SSL certificates in infra/ssl/"
	@echo "Required files: server.crt, server.key"

# Environment Variables
check-env:
	@echo "Checking environment configuration..."
	@test -f .env || (echo ".env file not found. Run 'make setup-dev' first." && exit 1)
	@echo "Environment configuration OK"

# Performance Testing
load-test:
	docker-compose exec web python manage.py test_performance

# Security Scanning
security-scan:
	docker run --rm -v "$(PWD):/app" sonarqube/sonar-scanner-cli

# Documentation
docs:
	@echo "API Documentation: http://localhost:8000/api/docs/"
	@echo "Admin Interface: http://localhost:8000/admin/"
	@echo "PWA Interface: http://localhost:8000/app/"

# Pre-commit Setup
setup-pre-commit:
	docker-compose exec web pre-commit install
	docker-compose exec web pre-commit run --all-files
