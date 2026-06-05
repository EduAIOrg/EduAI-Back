# Guide de Test - EduAI Africa Backend (Architecture Phase 2)

## 📋 Prérequis

Avant de tester l'application, assurez-vous d'avoir installé :

- Python 3.11+ (Recommandé: Python 3.12.7)
- PostgreSQL 14+ (avec l'extension pgvector)
- Supabase Storage (optionnel pour le stockage dans le cloud, sinon stockage local configuré)
- Serveurs TEI (Text Embeddings Inference) pour les embeddings (`multilingual-e5-large`) et le reranking (`bge-reranker-large`)
- Modèle vLLM (`Qwen3-Instruct`) configuré dans votre `.env`

---

## 🚀 Installation & Démarrage

### 1. Activer l'environnement virtuel et installer les dépendances

```bash
cd /home/samuelsean/Downloads/EduAI/EduAI-Back
source venv/bin/activate

# Installer les dépendances (y compris sse-starlette)
pip install -r requirements.txt
```

### 2. Migrations de Base de Données (Phase 2)

Les tables nécessaires aux nouvelles fonctionnalités (conversational memory, SaaS usage logs, feedbacks, observability) sont incluses dans les migrations Alembic :

```bash
# Vérifier la connexion à la base Railway / Locale et appliquer les migrations
alembic upgrade head
```

### 3. Exécuter le Script de Vérification

Pour vous assurer que tous les modules et dossiers requis sont en place, exécutez le script d'installation :

```bash
python verify_installation.py
```

---

## 🧪 Lancer les Tests Unitaires

Exécutez la suite de tests pour valider la robustesse de l'authentification et des services IA :

```bash
# Lancer tous les tests unitaires
./venv/bin/pytest -v
```

---

## 🏃 Démarrage des Services

### 1. Démarrer le serveur FastAPI

```bash
# Mode développement avec rechargement automatique
./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera accessible sur : **http://localhost:8000**
Documentation Swagger : **http://localhost:8000/docs**

---

## 🔍 Validation des Fonctionnalités Phase 2

### 1. Détection des doublons PDF par Hash SHA256

Lors de l'upload d'un document, le système calcule le hash SHA256 du fichier :
- **Même utilisateur** : Retourne immédiatement les métadonnées existantes.
- **Utilisateur différent (Doublon global)** : Crée une nouvelle référence mais copie instantanément les chunks de la base de données sans ré-exécuter le traitement d'embedding.

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/chemin/vers/votre/document.pdf" \
  -F "title=Document de Test"
```

### 2. Chat RAG avec Citations des sources & Streaming SSE

Le message de réponse IA commence par renvoyer les citations exactes de sources sous format JSON :
```json
{
  "sources": [
    {
      "document": "cours_algo.pdf",
      "page": 12,
      "score": 0.91,
      "content": "..."
    }
  ]
}
```
Puis, diffuse les jetons textuels via `EventSourceResponse` (format SSE standard).

#### Commande de Test :
```bash
curl -X POST http://localhost:8000/api/chat/conversations/{conversation_id}/messages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Quelle est la définition de la récursivité ?"
  }' \
  --no-buffer
```

### 3. Mémoire Conversationnelle LangGraph & Résumé Automatique

Le système stocke l'historique dans les tables PostgreSQL `chat_sessions` et `chat_messages` :
- Les 10 derniers messages sont injectés comme contexte court-terme.
- À partir de 10 messages, un résumé automatique (`chat_summaries`) est généré via le LLM et injecté dans le contexte du système pour préserver la mémoire à long terme.

### 4. Sécurité RAG : Filtres Anti-Jailbreak & Sanitizer

Toute question suspecte (ex. "ignore previous instructions") est bloquée par le `PromptInjectionDetector`. Le contenu extrait des fichiers est nettoyé par `ContextSanitizer` pour supprimer les balises HTML/Scripting malveillantes.

### 5. Observabilité IA (llm_requests, embedding_requests, reranking_requests)

Chaque requête IA enregistre sa latence en millisecondes, le modèle utilisé et le nombre de tokens dans la base de données.
Vous pouvez vérifier ces enregistrements directement dans PostgreSQL dans les tables `llm_requests`, `embedding_requests` et `reranking_requests`.

### 6. Système de Feedback RAG (Likes / Dislikes / Commentaires)

Permet aux étudiants d'évaluer la qualité des réponses générées par le RAG.

#### Enregistrer un Feedback :
```bash
curl -X POST http://localhost:8000/api/chat/feedback \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "uuid-du-message-assistant",
    "is_positive": true,
    "comment": "Réponse très précise avec la bonne page de référence !"
  }'
```

#### Consulter les statistiques de Feedback :
```bash
curl -X GET http://localhost:8000/api/chat/feedback/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Enforcement des Quotas SaaS (Limites journalières)

Les limites du plan **Free** (par défaut) sont appliquées par jour glissant :
- Chats : 10 messages / jour
- Uploads de PDF : 3 documents / jour
- Quiz : 3 quiz / jour
- Transcriptions : 3 audios / jour

Si le quota est dépassé, l'API renvoie un code d'erreur `429 Too Many Requests`.
Les utilisateurs ayant le rôle premium (colonne `plan` de la table `users`) ont des quotas illimités.

---

## 🐛 Dépannage

### Erreur 429 lors des tests
Vérifiez le nombre d'entrées dans la table `usage_logs` pour l'utilisateur actuel aujourd'hui :
```sql
SELECT count(*), action_type FROM usage_logs WHERE user_id = 'YOUR_USER_ID' GROUP BY action_type;
```

---
Bon test ! 🚀
