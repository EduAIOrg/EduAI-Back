#!/bin/bash

# Script de démarrage pour EduAI Africa Backend

echo "🚀 Démarrage de EduAI Africa Backend..."

# Vérifier que l'environnement virtuel est activé
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Environnement virtuel non activé. Activation..."
    source venv/bin/activate
fi

# Vérifier que PostgreSQL est démarré
echo "🔍 Vérification de PostgreSQL..."
if ! pg_isready -q; then
    echo "❌ PostgreSQL n'est pas démarré. Démarrage..."
    sudo systemctl start postgresql
fi

# Vérifier que Redis est démarré
echo "🔍 Vérification de Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis n'est pas démarré. Démarrage..."
    sudo systemctl start redis
fi

# Créer les dossiers nécessaires
echo "📁 Création des dossiers..."
mkdir -p uploads chroma_db logs

# Appliquer les migrations
echo "🗄️  Application des migrations..."
alembic upgrade head

# Démarrer l'application
echo "✅ Démarrage de l'application FastAPI..."
echo "📚 Documentation disponible sur: http://localhost:8000/docs"
echo ""
echo "⚠️  N'oubliez pas de démarrer Celery dans un autre terminal:"
echo "   celery -A app.celery_app worker --loglevel=info"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
