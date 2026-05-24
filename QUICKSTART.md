# ⚡ Quick Start - EduAI Africa Backend

Guide de démarrage rapide en 5 minutes !

---

## 🚀 Option 1: Démarrage avec Docker (Le Plus Rapide)

### Prérequis
- Docker et Docker Compose installés

### Étapes

```bash
# 1. Configurer les variables d'environnement
cp .env.example .env

# 2. Éditer .env et ajouter votre clé OpenAI
nano .env
# Modifier: OPENAI_API_KEY=sk-votre-clé-ici

# 3. Démarrer tous les services
docker-compose up -d

# 4. Appliquer les migrations
docker-compose exec api alembic upgrade head

# 5. Vérifier que tout fonctionne
curl http://localhost:8000/health
```

**✅ C'est tout ! L'API est disponible sur http://localhost:8000**

Documentation: http://localhost:8000/docs

---

## 🐍 Option 2: Démarrage Local

### Prérequis
- Python 3.11+
- PostgreSQL 14+
- Redis 6+

### Étapes

```bash
# 1. Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Vérifier l'installation
python verify_installation.py

# 4. Créer la base de données PostgreSQL
sudo -u postgres psql
CREATE DATABASE eduai;
CREATE USER eduai WITH PASSWORD 'eduai_password';
GRANT ALL PRIVILEGES ON DATABASE eduai TO eduai;
\q

# 5. Configurer .env
cp .env.example .env
nano .env
# Modifier:
#   DATABASE_URL=postgresql+asyncpg://eduai:eduai_password@localhost:5432/eduai
#   OPENAI_API_KEY=sk-votre-clé-ici

# 6. Appliquer les migrations
alembic upgrade head

# 7. Démarrer l'application (Terminal 1)
uvicorn app.main:app --reload

# 8. Démarrer Celery (Terminal 2)
celery -A app.celery_app worker --loglevel=info
```

**✅ L'API est disponible sur http://localhost:8000**

---

## 🧪 Test Rapide

### 1. Créer un compte

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

**Réponse:** Vous recevrez un `access_token`

### 2. Tester l'authentification

```bash
# Remplacer YOUR_TOKEN par le token reçu
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Uploader un document PDF

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/chemin/vers/document.pdf" \
  -F "title=Mon Premier Document"
```

### 4. Vérifier le traitement

```bash
# Remplacer DOCUMENT_ID par l'ID reçu
curl -X GET http://localhost:8000/api/documents/DOCUMENT_ID/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📚 Documentation Complète

- **Guide de Test Complet**: [testing.md](testing.md)
- **Documentation API**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Guide de Déploiement**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Résumé du Projet**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **Swagger UI**: http://localhost:8000/docs

---

## 🛠️ Commandes Utiles (Makefile)

```bash
make help          # Voir toutes les commandes
make install       # Installer les dépendances
make dev           # Démarrer en mode dev
make celery        # Démarrer Celery
make test          # Lancer les tests
make migrate       # Créer une migration
make upgrade       # Appliquer les migrations
make docker-up     # Démarrer avec Docker
make clean         # Nettoyer les fichiers temp
```

---

## ⚙️ Configuration Minimale (.env)

```env
# Base de données
DATABASE_URL=postgresql+asyncpg://eduai:eduai_password@localhost:5432/eduai

# Redis
REDIS_URL=redis://localhost:6379/0

# Sécurité (générer avec: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=votre-clé-secrète-aléatoire-ici

# OpenAI (OBLIGATOIRE)
OPENAI_API_KEY=sk-votre-clé-openai-ici

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 🔧 Dépannage Rapide

### Erreur: "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### Erreur: "Connection refused" (PostgreSQL)
```bash
sudo systemctl start postgresql
```

### Erreur: "Connection refused" (Redis)
```bash
sudo systemctl start redis
```

### Erreur: "Invalid OpenAI API key"
```bash
# Vérifier que OPENAI_API_KEY est bien configuré dans .env
# Ou utiliser Ollama: USE_OLLAMA=true
```

### Document reste en "processing"
```bash
# Vérifier que Celery tourne
celery -A app.celery_app inspect active

# Vérifier les logs Celery
celery -A app.celery_app worker --loglevel=debug
```

---

## 📊 Endpoints Principaux

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | Documentation Swagger |
| `/api/auth/register` | POST | Inscription |
| `/api/auth/login` | POST | Connexion |
| `/api/documents/` | POST | Upload PDF |
| `/api/chat/conversations` | POST | Créer conversation |
| `/api/quiz/generate` | POST | Générer quiz |

---

## 🎯 Workflow Complet

```
1. Inscription/Connexion
   ↓
2. Upload Document PDF
   ↓
3. Attendre traitement (status: ready)
   ↓
4. Créer Conversation
   ↓
5. Poser des questions (Chat RAG)
   ↓
6. Générer Quiz
   ↓
7. Passer le Quiz
   ↓
8. Voir les Résultats + Lacunes
```

---

## 🎉 Vous êtes prêt !

L'application est maintenant opérationnelle. Consultez:
- **testing.md** pour des tests détaillés
- **API_DOCUMENTATION.md** pour tous les endpoints
- **http://localhost:8000/docs** pour tester l'API interactivement

**Bon développement ! 🚀**
