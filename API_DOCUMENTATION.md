# 📚 Documentation API - EduAI Africa

## Base URL
```
http://localhost:8000/api
```

## Authentication

Tous les endpoints (sauf `/auth/register` et `/auth/login`) nécessitent un token JWT dans le header:

```
Authorization: Bearer <votre_token>
```

---

## 🔐 Authentication Endpoints

### POST /auth/register
Créer un nouveau compte utilisateur.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

### POST /auth/login
Se connecter avec email et mot de passe.

**Request Body (form-data):**
```
username: user@example.com
password: password123
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

### GET /auth/me
Obtenir les informations de l'utilisateur connecté.

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

## 📄 Documents Endpoints

### GET /documents/
Lister tous les documents de l'utilisateur.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "title": "Mon Document",
    "filename": "/path/to/file.pdf",
    "file_size": 1234567,
    "page_count": 10,
    "status": "ready",
    "summary": "Résumé du document...",
    "chroma_collection_id": "doc_uuid",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### POST /documents/
Uploader un nouveau document PDF.

**Request (multipart/form-data):**
```
file: <fichier.pdf>
title: "Titre du document" (optionnel)
```

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Mon Document",
  "filename": "/path/to/file.pdf",
  "file_size": 1234567,
  "page_count": 0,
  "status": "uploading",
  "summary": null,
  "chroma_collection_id": null,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### GET /documents/{document_id}
Obtenir les détails d'un document.

**Response (200):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Mon Document",
  "filename": "/path/to/file.pdf",
  "file_size": 1234567,
  "page_count": 10,
  "status": "ready",
  "summary": "Résumé complet...",
  "chroma_collection_id": "doc_uuid",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### GET /documents/{document_id}/status
Vérifier le statut de traitement d'un document.

**Response (200):**
```json
{
  "status": "processing",
  "progress_message": "Traitement du document en cours..."
}
```

**Statuts possibles:**
- `uploading`: Téléchargement en cours
- `processing`: Traitement en cours
- `ready`: Prêt
- `error`: Erreur

### GET /documents/{document_id}/summary
Obtenir uniquement le résumé d'un document.

**Response (200):**
```json
{
  "summary": "Résumé du document...",
  "status": "ready"
}
```

### DELETE /documents/{document_id}
Supprimer un document.

**Response (204):** No Content

---

## 💬 Chat Endpoints

### GET /chat/conversations
Lister toutes les conversations.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "title": "Discussion sur le document",
    "created_at": "2024-01-01T00:00:00Z",
    "last_message": "Dernière question...",
    "message_count": 5
  }
]
```

### POST /chat/conversations
Créer une nouvelle conversation.

**Request Body:**
```json
{
  "document_id": "uuid",  // optionnel
  "title": "Ma conversation"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "document_id": "uuid",
  "title": "Ma conversation",
  "created_at": "2024-01-01T00:00:00Z",
  "messages": []
}
```

### GET /chat/conversations/{conversation_id}/messages
Obtenir tous les messages d'une conversation.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "Ma question",
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "Ma réponse",
    "created_at": "2024-01-01T00:00:01Z"
  }
]
```

### POST /chat/conversations/{conversation_id}/messages
Envoyer un message et recevoir la réponse en streaming (SSE).

**Request Body:**
```json
{
  "content": "Explique-moi ce concept"
}
```

**Response (200 - text/event-stream):**
```
data: {"token": "Voici"}

data: {"token": " l'explication"}

data: {"token": "..."}

data: {"done": true, "message_id": "uuid"}
```

### DELETE /chat/conversations/{conversation_id}
Supprimer une conversation.

**Response (204):** No Content

---

## 📝 Quiz Endpoints

### GET /quiz/
Lister tous les quiz.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "title": "Quiz sur le document",
    "quiz_type": "mixed",
    "difficulty": "medium",
    "status": "ready",
    "created_at": "2024-01-01T00:00:00Z",
    "question_count": 10,
    "last_score": 0.85
  }
]
```

### POST /quiz/generate
Générer un nouveau quiz.

**Request Body:**
```json
{
  "document_id": "uuid",
  "quiz_type": "mixed",  // "mcq", "open", "mixed"
  "difficulty": "medium",  // "easy", "medium", "hard"
  "num_questions": 10,
  "title": "Mon Quiz"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "document_id": "uuid",
  "title": "Mon Quiz",
  "quiz_type": "mixed",
  "difficulty": "medium",
  "status": "generating",
  "created_at": "2024-01-01T00:00:00Z",
  "questions": []
}
```

### GET /quiz/{quiz_id}
Obtenir un quiz avec ses questions.

**Response (200):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "document_id": "uuid",
  "title": "Mon Quiz",
  "quiz_type": "mixed",
  "difficulty": "medium",
  "status": "ready",
  "created_at": "2024-01-01T00:00:00Z",
  "questions": [
    {
      "id": "uuid",
      "quiz_id": "uuid",
      "content": "Quelle est la réponse?",
      "question_type": "mcq",
      "options": ["A", "B", "C", "D"],
      "order_index": 0
    }
  ]
}
```

### GET /quiz/{quiz_id}/status
Vérifier le statut de génération.

**Response (200):**
```json
{
  "status": "generating",
  "progress_message": "Génération du quiz en cours..."
}
```

### POST /quiz/{quiz_id}/submit
Soumettre les réponses du quiz.

**Request Body:**
```json
{
  "answers": [
    {
      "question_id": "uuid",
      "answer": "A"
    },
    {
      "question_id": "uuid",
      "answer": "Ma réponse détaillée"
    }
  ],
  "time_spent": 300
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "quiz_id": "uuid",
  "user_id": "uuid",
  "score": 0.85,
  "time_spent": 300,
  "created_at": "2024-01-01T00:00:00Z",
  "answer_feedback": [
    {
      "question_id": "uuid",
      "is_correct": true,
      "score": 1.0,
      "user_answer": "A",
      "correct_answer": "A",
      "feedback": "Correct! Explication..."
    }
  ],
  "lacunes": [
    {
      "notion": "Concept X",
      "level": "weak",
      "last_seen": "2024-01-01T00:00:00Z",
      "recommendations": ["Revoir le chapitre 3", "Faire des exercices"]
    }
  ]
}
```

### GET /quiz/{quiz_id}/results
Obtenir tous les résultats d'un quiz.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "quiz_id": "uuid",
    "user_id": "uuid",
    "score": 0.85,
    "time_spent": 300,
    "created_at": "2024-01-01T00:00:00Z",
    "answer_feedback": [...],
    "lacunes": [...]
  }
]
```

---

## 🌍 Translation Endpoint

### POST /translate/
Traduire du texte.

**Request Body:**
```json
{
  "text": "Bonjour, comment allez-vous?",
  "source_lang": "fr",
  "target_lang": "en",
  "preserve_pedagogical_context": true
}
```

**Response (200):**
```json
{
  "translated_text": "Hello, how are you?",
  "source_lang": "fr",
  "target_lang": "en"
}
```

---

## 🎤 Voice Endpoints

### POST /voice/transcribe
Transcrire un fichier audio.

**Request (multipart/form-data):**
```
audio: <fichier.webm>
```

**Response (200):**
```json
{
  "transcript": "Texte transcrit de l'audio..."
}
```

### POST /voice/synthesize
Synthétiser de la parole.

**Request Body:**
```json
{
  "text": "Texte à synthétiser",
  "lang": "fr"
}
```

**Response (200):** Audio stream (audio/mpeg)

---

## ❌ Codes d'Erreur

### 400 Bad Request
Requête invalide (validation échouée).

```json
{
  "detail": "Message d'erreur"
}
```

### 401 Unauthorized
Token manquant ou invalide.

```json
{
  "detail": "Invalid authentication credentials"
}
```

### 403 Forbidden
Accès refusé (pas propriétaire de la ressource).

```json
{
  "detail": "Access denied"
}
```

### 404 Not Found
Ressource non trouvée.

```json
{
  "detail": "Resource not found"
}
```

### 413 Request Entity Too Large
Fichier trop volumineux.

```json
{
  "detail": "File size exceeds maximum of 50MB"
}
```

### 422 Unprocessable Entity
Erreur de validation Pydantic.

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### 500 Internal Server Error
Erreur serveur.

```json
{
  "detail": "Internal server error"
}
```

---

## 📊 Rate Limiting

- **Login endpoint**: 10 requêtes par minute par IP
- **Autres endpoints**: Pas de limite (à configurer selon les besoins)

---

## 🔄 Workflow Typique

### 1. Inscription et Connexion
```
POST /auth/register → Obtenir token
OU
POST /auth/login → Obtenir token
```

### 2. Upload et Traitement de Document
```
POST /documents/ → Upload PDF
GET /documents/{id}/status → Vérifier statut (polling)
GET /documents/{id} → Obtenir document complet avec résumé
```

### 3. Chat avec le Document
```
POST /chat/conversations → Créer conversation
POST /chat/conversations/{id}/messages → Envoyer message (SSE)
GET /chat/conversations/{id}/messages → Historique
```

### 4. Génération et Passage de Quiz
```
POST /quiz/generate → Générer quiz
GET /quiz/{id}/status → Vérifier statut (polling)
GET /quiz/{id} → Obtenir questions
POST /quiz/{id}/submit → Soumettre réponses
GET /quiz/{id}/results → Voir résultats
```

---

## 🔧 Headers Recommandés

```
Content-Type: application/json
Authorization: Bearer <token>
Accept: application/json
```

Pour le streaming SSE:
```
Accept: text/event-stream
```

---

## 📝 Notes

- Tous les timestamps sont en UTC (ISO 8601)
- Les UUIDs sont au format standard (avec tirets)
- Les fichiers PDF doivent être valides et < 50MB
- Le streaming SSE nécessite un client compatible
- Les tâches async (document, quiz) utilisent Celery

---

Pour plus de détails, consultez la documentation interactive Swagger UI à `/docs`.
