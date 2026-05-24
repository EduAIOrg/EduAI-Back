#!/bin/bash

# Script de démarrage pour Celery Worker

echo "🔧 Démarrage de Celery Worker..."

# Vérifier que l'environnement virtuel est activé
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Environnement virtuel non activé. Activation..."
    source venv/bin/activate
fi

# Vérifier que Redis est démarré
echo "🔍 Vérification de Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis n'est pas démarré. Démarrage..."
    sudo systemctl start redis
fi

# Démarrer Celery worker
echo "✅ Démarrage du worker Celery..."
celery -A app.celery_app worker --loglevel=info --concurrency=4
