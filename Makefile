.PHONY: help install dev test clean migrate upgrade downgrade celery docker-up docker-down

help:
	@echo "EduAI Africa Backend - Commandes disponibles:"
	@echo ""
	@echo "  make install      - Installer les dépendances"
	@echo "  make dev          - Démarrer en mode développement"
	@echo "  make test         - Lancer les tests"
	@echo "  make test-cov     - Lancer les tests avec couverture"
	@echo "  make clean        - Nettoyer les fichiers temporaires"
	@echo "  make migrate      - Créer une nouvelle migration"
	@echo "  make upgrade      - Appliquer les migrations"
	@echo "  make downgrade    - Revenir à la migration précédente"
	@echo "  make celery       - Démarrer Celery worker"
	@echo "  make docker-up    - Démarrer avec Docker Compose"
	@echo "  make docker-down  - Arrêter Docker Compose"
	@echo "  make lint         - Vérifier le code avec flake8"
	@echo "  make format       - Formater le code avec black"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=app --cov-report=html --cov-report=term

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

celery:
	celery -A app.celery_app worker --loglevel=info --concurrency=4

celery-beat:
	celery -A app.celery_app beat --loglevel=info

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

lint:
	flake8 app/ --max-line-length=120 --exclude=__pycache__,migrations

format:
	black app/ tests/ --line-length=100

setup-db:
	@echo "Création de la base de données PostgreSQL..."
	sudo -u postgres psql -c "CREATE DATABASE eduai;"
	sudo -u postgres psql -c "CREATE USER eduai WITH PASSWORD 'eduai_password';"
	sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE eduai TO eduai;"
	@echo "Base de données créée avec succès!"

init:
	@echo "Initialisation du projet..."
	python3 -m venv venv
	@echo "Activez l'environnement virtuel avec: source venv/bin/activate"
	@echo "Puis lancez: make install && make setup-db && make upgrade"
