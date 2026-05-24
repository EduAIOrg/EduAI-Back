#!/usr/bin/env python3
"""Script de vérification de l'installation EduAI Africa Backend."""

import sys
import importlib
from pathlib import Path


def check_python_version():
    """Vérifier la version de Python."""
    print("🐍 Vérification de la version Python...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (requis: 3.11+)")
        return False


def check_dependencies():
    """Vérifier les dépendances principales."""
    print("\n📦 Vérification des dépendances...")
    
    dependencies = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "asyncpg",
        "pydantic",
        "pydantic_settings",
        "langchain",
        "langchain_openai",
        "langchain_community",
        "chromadb",
        "fitz",  # PyMuPDF
        "celery",
        "redis",
        "jose",
        "passlib",
    ]
    
    all_ok = True
    for dep in dependencies:
        try:
            importlib.import_module(dep)
            print(f"   ✅ {dep}")
        except ImportError:
            print(f"   ❌ {dep} (non installé)")
            all_ok = False
    
    return all_ok


def check_project_structure():
    """Vérifier la structure du projet."""
    print("\n📁 Vérification de la structure du projet...")
    
    required_paths = [
        "app/main.py",
        "app/config.py",
        "app/database.py",
        "app/models/user.py",
        "app/models/document.py",
        "app/models/chat.py",
        "app/models/quiz.py",
        "app/schemas/auth.py",
        "app/routers/auth.py",
        "app/routers/documents.py",
        "app/routers/chat.py",
        "app/routers/quiz.py",
        "app/services/auth_service.py",
        "app/services/document_service.py",
        "app/services/rag_service.py",
        "app/services/quiz_service.py",
        "app/tasks/document_tasks.py",
        "app/tasks/quiz_tasks.py",
        "app/ai/llm_factory.py",
        "app/ai/embeddings.py",
        "app/ai/vector_store.py",
        "app/ai/prompts.py",
        "app/utils/pdf_utils.py",
        "app/utils/text_utils.py",
        "requirements.txt",
        "alembic.ini",
        ".env.example",
    ]
    
    all_ok = True
    for path in required_paths:
        if Path(path).exists():
            print(f"   ✅ {path}")
        else:
            print(f"   ❌ {path} (manquant)")
            all_ok = False
    
    return all_ok


def check_env_file():
    """Vérifier le fichier .env."""
    print("\n⚙️  Vérification de la configuration...")
    
    if Path(".env").exists():
        print("   ✅ Fichier .env existe")
        
        # Lire et vérifier les variables essentielles
        with open(".env", "r") as f:
            content = f.read()
            
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
        ]
        
        all_ok = True
        for var in required_vars:
            if var in content:
                print(f"   ✅ {var} configuré")
            else:
                print(f"   ⚠️  {var} non configuré")
                all_ok = False
        
        return all_ok
    else:
        print("   ⚠️  Fichier .env n'existe pas")
        print("   💡 Copiez .env.example vers .env et configurez-le")
        return False


def check_directories():
    """Vérifier les dossiers nécessaires."""
    print("\n📂 Vérification des dossiers...")
    
    required_dirs = [
        "uploads",
        "chroma_db",
        "app/migrations/versions",
    ]
    
    all_ok = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print(f"   ✅ {dir_path}/")
        else:
            print(f"   ⚠️  {dir_path}/ (sera créé au démarrage)")
    
    return True


def check_imports():
    """Vérifier que les modules app peuvent être importés."""
    print("\n🔍 Vérification des imports app...")
    
    try:
        from app.config import settings
        print(f"   ✅ app.config (APP_NAME: {settings.APP_NAME})")
    except Exception as e:
        print(f"   ❌ app.config: {e}")
        return False
    
    try:
        from app.database import Base
        print("   ✅ app.database")
    except Exception as e:
        print(f"   ❌ app.database: {e}")
        return False
    
    try:
        from app.models.user import User
        print("   ✅ app.models.user")
    except Exception as e:
        print(f"   ❌ app.models.user: {e}")
        return False
    
    try:
        from app.services.auth_service import AuthService
        print("   ✅ app.services.auth_service")
    except Exception as e:
        print(f"   ❌ app.services.auth_service: {e}")
        return False
    
    return True


def main():
    """Fonction principale."""
    print("=" * 60)
    print("🎓 EduAI Africa Backend - Vérification de l'Installation")
    print("=" * 60)
    
    checks = [
        ("Version Python", check_python_version),
        ("Dépendances", check_dependencies),
        ("Structure du projet", check_project_structure),
        ("Configuration", check_env_file),
        ("Dossiers", check_directories),
        ("Imports", check_imports),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Erreur lors de la vérification de {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ OK" if result else "❌ ÉCHEC"
        print(f"{status:10} - {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 Toutes les vérifications sont passées !")
        print("\n📝 Prochaines étapes:")
        print("   1. Configurer PostgreSQL: make setup-db")
        print("   2. Appliquer les migrations: make upgrade")
        print("   3. Démarrer l'application: make dev")
        print("   4. Démarrer Celery: make celery")
        print("\n📚 Consultez testing.md pour plus de détails")
        return 0
    else:
        print("\n⚠️  Certaines vérifications ont échoué.")
        print("\n📝 Actions recommandées:")
        print("   1. Installer les dépendances: pip install -r requirements.txt")
        print("   2. Créer le fichier .env: cp .env.example .env")
        print("   3. Configurer les variables dans .env")
        print("\n📚 Consultez README.md pour plus de détails")
        return 1


if __name__ == "__main__":
    sys.exit(main())
