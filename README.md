# 🎓 EduAI Africa - Backend API

Assistant IA pédagogique intelligent pour l'éducation en Afrique.

## 🌟 Fonctionnalités

### 📚 Gestion de Documents
- Upload de documents PDF
- Extraction et traitement automatique du texte
- Génération de résumés intelligents
- Indexation vectorielle avec ChromaDB
- Recherche sémantique dans les documents

### 💬 Chat Intelligent (RAG)
- Chat contextuel basé sur les documents
- Streaming des réponses en temps réel (SSE)
- Historique de conversation
- Mode chat général (sans document)

### 📝 Génération de Quiz
- Génération automatique de questions (QCM et ouvertes)
- Trois niveaux de difficulté (facile, moyen, difficile)
- Évaluation automatique des réponses
- Feedback détaillé et pédagogique
- Analyse des lacunes d'apprentissage

### 🌍 Traduction
- Traduction français ↔ anglais
- Préservation du contexte pédagogique
- Terminologie académique respectée

### 🎤 Fonctionnalités Vocales
- Transcription audio (Whisper)
- Support multilingue

### 📊 Suivi de Progression
- Historique des quiz
- Analyse des lacunes
- Recommandations personnalisées
- Statistiques de performance

## 🏗️ Architecture Technique

### Stack
- **Framework**: FastAPI 0.115+
- **Base de données**: PostgreSQL 14+ (async avec asyncpg)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Cache/Queue**: Redis
- **Tâches async**: Celery
- **IA/LLM**: LangChain 0.3+ avec OpenAI ou Ollama
- **Embeddings**: OpenAI text-embedding-3-small ou Ollama nomic-embed-text
- **Vector Store**: ChromaDB (persistant)
- **PDF Processing**: PyMuPDF (fitz)
- **Auth**: JWT (python-jose + passlib)

### Structure du Projet

```
app/
├── main.py                 # Application FastAPI principale
├── config.py               # Configuration (Pydantic Settings)
├── database.py             # Configuration SQLAlchemy async
├── dependencies.py         # Dépendances FastAPI (auth, db)
├── celery_app.py          # Configuration Celery
│
├── models/                 # Modèles SQLAlchemy
│   ├── user.py
│   ├── document.py
│   ├── chat.py
│   └── quiz.py
│
├── schemas/                # Schémas Pydantic
│   ├── auth.py
│   ├── document.py
│   ├── chat.py
│   ├── quiz.py
│   └── translate.py
│
├── routers/                # Endpoints API
│   ├── auth.py
│   ├── documents.py
│   ├── chat.py
│   ├── quiz.py
│   ├── translate.py
│   └── voice.py
│
├── services/               # Logique métier
│   ├── auth_service.py
│   ├── document_service.py
│   ├── rag_service.py
│   ├── quiz_service.py
│   ├── lacune_service.py
│   ├── translate_service.py
│   └── voice_service.py
│
├── tasks/                  # Tâches Celery
│   ├── document_tasks.py
│   └── quiz_tasks.py
│
├── ai/                     # Composants IA
│   ├── llm_factory.py
│   ├── embeddings.py
│   ├── vector_store.py
│   └── prompts.py
│
├── utils/                  # Utilitaires
│   ├── pdf_utils.py
│   └── text_utils.py
│
└── migrations/             # Migrations Alembic
    └── versions/
```

## 🚀 Installation

### Prérequis
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- (Optionnel) Ollama pour modèles locaux

### Installation rapide

```bash
# Cloner le projet
git clone <repo-url>
cd EduAI-Back

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs

# Créer la base de données
sudo -u postgres psql
CREATE DATABASE eduai;
CREATE USER eduai WITH PASSWORD 'eduai_password';
GRANT ALL PRIVILEGES ON DATABASE eduai TO eduai;
\q

# Appliquer les migrations
alembic upgrade head

# Démarrer l'application
uvicorn app.main:app --reload

# Dans un autre terminal, démarrer Celery
celery -A app.celery_app worker --loglevel=info
```

## 📖 Documentation

### API Documentation
Une fois l'application démarrée :
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Guide de Test
Voir [testing.md](testing.md) pour un guide complet de test.

## 🔑 Endpoints Principaux

### Authentication
- `POST /api/auth/register` - Inscription
- `POST /api/auth/login` - Connexion
- `GET /api/auth/me` - Profil utilisateur

### Documents
- `GET /api/documents/` - Liste des documents
- `POST /api/documents/` - Upload document
- `GET /api/documents/{id}` - Détails document
- `GET /api/documents/{id}/status` - Statut traitement
- `GET /api/documents/{id}/summary` - Résumé
- `DELETE /api/documents/{id}` - Supprimer

### Chat
- `GET /api/chat/conversations` - Liste conversations
- `POST /api/chat/conversations` - Créer conversation
- `GET /api/chat/conversations/{id}/messages` - Messages
- `POST /api/chat/conversations/{id}/messages` - Envoyer message (SSE)
- `DELETE /api/chat/conversations/{id}` - Supprimer

### Quiz
- `GET /api/quiz/` - Liste quiz
- `POST /api/quiz/generate` - Générer quiz
- `GET /api/quiz/{id}` - Détails quiz
- `GET /api/quiz/{id}/status` - Statut génération
- `POST /api/quiz/{id}/submit` - Soumettre réponses
- `GET /api/quiz/{id}/results` - Résultats

### Translation
- `POST /api/translate/` - Traduire texte

### Voice
- `POST /api/voice/transcribe` - Transcrire audio

## 🔒 Sécurité

- **Authentication**: JWT avec expiration configurable
- **Password Hashing**: bcrypt avec salt automatique
- **CORS**: Origines configurables
- **Rate Limiting**: 10 req/min sur login
- **File Validation**: Type MIME et taille max
- **Ownership Check**: Vérification sur toutes les ressources

## 🧪 Tests

```bash
# Lancer tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=app --cov-report=html
```

## 📊 Monitoring

### Logs
```bash
# Logs application
tail -f app.log

# Logs Celery
celery -A app.celery_app inspect active
```

### Health Check
```bash
curl http://localhost:8000/health
```

## 🌐 Variables d'Environnement

Voir `.env.example` pour la liste complète.

Variables essentielles :
- `DATABASE_URL` - URL PostgreSQL
- `REDIS_URL` - URL Redis
- `SECRET_KEY` - Clé secrète JWT
- `OPENAI_API_KEY` - Clé API OpenAI
- `USE_OLLAMA` - Utiliser Ollama (true/false)

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 License

Ce projet est sous licence MIT.

## 👥 Auteurs

EduAI Africa Team

## 🙏 Remerciements

- OpenAI pour les modèles GPT et Whisper
- LangChain pour le framework RAG
- FastAPI pour le framework web
- La communauté open source

---

**Note**: Ce backend est conçu pour être utilisé avec le frontend EduAI Africa (React/Next.js).
