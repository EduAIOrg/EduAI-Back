# Guide de Test - EduAI Africa Backend

## 📋 Prérequis

Avant de tester l'application, assurez-vous d'avoir installé :

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- (Optionnel) Ollama pour les modèles locaux

## 🚀 Installation

### 1. Cloner et installer les dépendances

```bash
cd /home/samuelsean/Downloads/EduAI-Back

# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration de la base de données PostgreSQL

```bash
# Se connecter à PostgreSQL
sudo -u postgres psql

# Créer la base de données et l'utilisateur
CREATE DATABASE eduai;
CREATE USER eduai WITH PASSWORD 'eduai_password';
GRANT ALL PRIVILEGES ON DATABASE eduai TO eduai;
\q
```

### 3. Configuration de Redis

```bash
# Démarrer Redis (si pas déjà démarré)
sudo systemctl start redis
# ou
redis-server
```

### 4. Configuration des variables d'environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer le fichier .env avec vos valeurs
nano .env
```

**Variables importantes à configurer :**

```env
# Database
DATABASE_URL=postgresql+asyncpg://eduai:eduai_password@localhost:5432/eduai

# OpenAI (OBLIGATOIRE pour les fonctionnalités IA)
OPENAI_API_KEY=sk-votre-clé-openai-ici

# Ou utiliser Ollama (alternative locale)
USE_OLLAMA=false
OLLAMA_BASE_URL=http://localhost:11434

# Security
SECRET_KEY=votre-clé-secrète-très-longue-et-aléatoire-ici
```

### 5. Initialiser la base de données avec Alembic

```bash
# Créer la première migration
alembic revision --autogenerate -m "Initial migration"

# Appliquer les migrations
alembic upgrade head
```

## 🧪 Lancer les Tests Unitaires

```bash
# Lancer tous les tests
pytest tests/ -v

# Lancer un fichier de test spécifique
pytest tests/test_auth_service.py -v

# Lancer avec couverture de code
pytest tests/ --cov=app --cov-report=html
```

## 🏃 Démarrer l'Application

### 1. Démarrer le serveur FastAPI

```bash
# Mode développement avec rechargement automatique
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Mode production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

L'API sera accessible sur : **http://localhost:8000**

Documentation interactive : **http://localhost:8000/docs**

### 2. Démarrer Celery Worker (dans un autre terminal)

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Démarrer le worker Celery
celery -A app.celery_app worker --loglevel=info
```

### 3. (Optionnel) Démarrer Celery Beat pour les tâches planifiées

```bash
celery -A app.celery_app beat --loglevel=info
```

## 🔍 Tests Manuels avec l'API

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Réponse attendue :**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "app": "EduAI Africa"
}
```

### 2. Inscription d'un utilisateur

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

**Réponse attendue :**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

### 3. Connexion

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=password123"
```

### 4. Obtenir les informations de l'utilisateur

```bash
# Remplacer YOUR_TOKEN par le token reçu
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Upload d'un document PDF

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/chemin/vers/votre/document.pdf" \
  -F "title=Mon Document de Test"
```

**Réponse attendue :**
```json
{
  "id": "uuid-du-document",
  "title": "Mon Document de Test",
  "status": "uploading",
  "file_size": 1234567,
  ...
}
```

### 6. Vérifier le statut du traitement du document

```bash
curl -X GET http://localhost:8000/api/documents/{document_id}/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Créer une conversation

```bash
curl -X POST http://localhost:8000/api/chat/conversations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-du-document",
    "title": "Discussion sur le document"
  }'
```

### 8. Envoyer un message (avec streaming SSE)

```bash
curl -X POST http://localhost:8000/api/chat/conversations/{conversation_id}/messages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Explique-moi le concept principal de ce document"
  }' \
  --no-buffer
```

### 9. Générer un quiz

```bash
curl -X POST http://localhost:8000/api/quiz/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-du-document",
    "quiz_type": "mixed",
    "difficulty": "medium",
    "num_questions": 10,
    "title": "Quiz de Test"
  }'
```

### 10. Vérifier le statut de génération du quiz

```bash
curl -X GET http://localhost:8000/api/quiz/{quiz_id}/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 11. Obtenir le quiz avec les questions

```bash
curl -X GET http://localhost:8000/api/quiz/{quiz_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 12. Soumettre les réponses du quiz

```bash
curl -X POST http://localhost:8000/api/quiz/{quiz_id}/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [
      {
        "question_id": "uuid-question-1",
        "answer": "A"
      },
      {
        "question_id": "uuid-question-2",
        "answer": "Ma réponse détaillée"
      }
    ],
    "time_spent": 300
  }'
```

### 13. Traduire du texte

```bash
curl -X POST http://localhost:8000/api/translate/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bonjour, comment allez-vous?",
    "source_lang": "fr",
    "target_lang": "en",
    "preserve_pedagogical_context": true
  }'
```

### 14. Transcrire un audio

```bash
curl -X POST http://localhost:8000/api/voice/transcribe \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "audio=@/chemin/vers/audio.webm"
```

### 15. Synthétiser de la parole

```bash
curl -X POST http://localhost:8000/api/voice/synthesize \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bonjour, ceci est un test de synthèse vocale.",
    "lang": "fr"
  }' \
  --output speech.mp3
```

## 🐛 Dépannage

### Problème : Erreur de connexion à PostgreSQL

**Solution :**
```bash
# Vérifier que PostgreSQL est démarré
sudo systemctl status postgresql

# Vérifier les credentials dans .env
# Tester la connexion manuellement
psql -U eduai -d eduai -h localhost
```

### Problème : Erreur de connexion à Redis

**Solution :**
```bash
# Vérifier que Redis est démarré
sudo systemctl status redis

# Tester la connexion
redis-cli ping
# Devrait retourner: PONG
```

### Problème : Celery worker ne démarre pas

**Solution :**
```bash
# Vérifier que Redis est accessible
redis-cli ping

# Vérifier les logs Celery
celery -A app.celery_app worker --loglevel=debug
```

### Problème : Erreur OpenAI API

**Solution :**
- Vérifier que `OPENAI_API_KEY` est correctement configuré dans `.env`
- Vérifier que vous avez des crédits sur votre compte OpenAI
- Ou basculer sur Ollama : `USE_OLLAMA=true`

### Problème : Document reste en statut "processing"

**Solution :**
```bash
# Vérifier les logs du worker Celery
# Vérifier que ChromaDB est accessible
# Vérifier l'espace disque disponible
df -h
```

## 📊 Monitoring

### Logs de l'application

```bash
# Logs FastAPI (dans le terminal où uvicorn tourne)
# Logs Celery (dans le terminal du worker)

# Pour sauvegarder les logs
uvicorn app.main:app --log-config logging.conf > app.log 2>&1
```

### Vérifier les tâches Celery

```bash
# Inspecter les tâches actives
celery -A app.celery_app inspect active

# Inspecter les tâches enregistrées
celery -A app.celery_app inspect registered
```

## 🔐 Sécurité

### Recommandations pour la production

1. **Changer le SECRET_KEY** : Générer une clé aléatoire forte
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Utiliser HTTPS** : Configurer un reverse proxy (Nginx/Caddy)

3. **Limiter les CORS** : Restreindre `ALLOWED_ORIGINS` aux domaines autorisés

4. **Sécuriser PostgreSQL** : Utiliser des mots de passe forts

5. **Rate limiting** : Déjà configuré sur `/auth/login` (10 req/min)

## 📚 Documentation Interactive

Une fois l'application démarrée, accédez à :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **OpenAPI JSON** : http://localhost:8000/openapi.json

## ✅ Checklist de Validation

- [ ] PostgreSQL installé et configuré
- [ ] Redis installé et démarré
- [ ] Variables d'environnement configurées
- [ ] Migrations Alembic appliquées
- [ ] Tests unitaires passent
- [ ] Serveur FastAPI démarre sans erreur
- [ ] Worker Celery démarre sans erreur
- [ ] Inscription utilisateur fonctionne
- [ ] Upload de document fonctionne
- [ ] Traitement de document fonctionne (vérifier les logs Celery)
- [ ] Chat avec RAG fonctionne
- [ ] Génération de quiz fonctionne
- [ ] Soumission de quiz fonctionne
- [ ] Traduction fonctionne
- [ ] Transcription audio fonctionne
- [ ] Synthèse vocale fonctionne

## 🎯 Prochaines Étapes

1. Tester avec un vrai document PDF
2. Tester le chat avec streaming SSE
3. Générer et passer un quiz complet
4. Vérifier l'analyse des lacunes
5. Tester la traduction pédagogique
6. Tester la transcription et synthèse vocale

## 📞 Support

Pour toute question ou problème :
- Vérifier les logs de l'application
- Vérifier les logs Celery
- Consulter la documentation Swagger UI
- Vérifier que tous les services (PostgreSQL, Redis) sont démarrés

Bon test ! 🚀
