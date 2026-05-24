# 🚀 Guide de Déploiement - EduAI Africa Backend

## Options de Déploiement

### 1. Déploiement Local (Développement)

Voir [testing.md](testing.md) pour les instructions détaillées.

**Résumé rapide:**
```bash
# Installation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Éditer .env

# Base de données
make setup-db
make upgrade

# Démarrage
make dev  # Terminal 1
make celery  # Terminal 2
```

---

### 2. Déploiement avec Docker Compose (Recommandé)

**Avantages:**
- Isolation complète
- PostgreSQL et Redis inclus
- Configuration simplifiée
- Facile à reproduire

**Instructions:**

```bash
# 1. Configurer .env
cp .env.example .env
# Éditer .env avec vos valeurs

# 2. Démarrer tous les services
docker-compose up -d

# 3. Vérifier les logs
docker-compose logs -f

# 4. Appliquer les migrations (première fois)
docker-compose exec api alembic upgrade head

# 5. Arrêter les services
docker-compose down
```

**Services disponibles:**
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

### 3. Déploiement sur VPS (Production)

#### Prérequis
- Ubuntu 20.04+ ou Debian 11+
- Accès root ou sudo
- Nom de domaine (optionnel mais recommandé)

#### Étape 1: Préparation du Serveur

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation des dépendances
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib redis-server \
    nginx certbot python3-certbot-nginx \
    git supervisor

# Créer un utilisateur pour l'application
sudo adduser eduai
sudo usermod -aG sudo eduai
su - eduai
```

#### Étape 2: Configuration PostgreSQL

```bash
sudo -u postgres psql

CREATE DATABASE eduai;
CREATE USER eduai WITH PASSWORD 'votre_mot_de_passe_fort';
GRANT ALL PRIVILEGES ON DATABASE eduai TO eduai;
\q
```

#### Étape 3: Cloner et Configurer l'Application

```bash
cd /home/eduai
git clone <votre-repo> eduai-backend
cd eduai-backend

# Créer l'environnement virtuel
python3.11 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer .env
cp .env.example .env
nano .env
```

**Configuration .env pour production:**
```env
DATABASE_URL=postgresql+asyncpg://eduai:votre_mot_de_passe@localhost:5432/eduai
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<générer avec: python -c "import secrets; print(secrets.token_urlsafe(32))">
OPENAI_API_KEY=sk-votre-clé
DEBUG=false
ALLOWED_ORIGINS=https://votre-domaine.com
```

#### Étape 4: Appliquer les Migrations

```bash
source venv/bin/activate
alembic upgrade head
```

#### Étape 5: Configuration Supervisor (FastAPI)

```bash
sudo nano /etc/supervisor/conf.d/eduai-api.conf
```

```ini
[program:eduai-api]
command=/home/eduai/eduai-backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
directory=/home/eduai/eduai-backend
user=eduai
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/eduai/eduai-backend/logs/api.log
environment=PATH="/home/eduai/eduai-backend/venv/bin"
```

#### Étape 6: Configuration Supervisor (Celery)

```bash
sudo nano /etc/supervisor/conf.d/eduai-celery.conf
```

```ini
[program:eduai-celery]
command=/home/eduai/eduai-backend/venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=4
directory=/home/eduai/eduai-backend
user=eduai
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/eduai/eduai-backend/logs/celery.log
environment=PATH="/home/eduai/eduai-backend/venv/bin"
```

#### Étape 7: Démarrer les Services

```bash
# Créer le dossier logs
mkdir -p /home/eduai/eduai-backend/logs

# Recharger Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Démarrer les services
sudo supervisorctl start eduai-api
sudo supervisorctl start eduai-celery

# Vérifier le statut
sudo supervisorctl status
```

#### Étape 8: Configuration Nginx

```bash
sudo nano /etc/nginx/sites-available/eduai
```

```nginx
server {
    listen 80;
    server_name votre-domaine.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Pour le streaming SSE
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }

    location /static {
        alias /home/eduai/eduai-backend/uploads;
    }
}
```

```bash
# Activer le site
sudo ln -s /etc/nginx/sites-available/eduai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Étape 9: SSL avec Let's Encrypt

```bash
sudo certbot --nginx -d votre-domaine.com
```

#### Étape 10: Configuration du Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

### 4. Déploiement sur Cloud (AWS, GCP, Azure)

#### AWS EC2

**1. Lancer une instance EC2**
- AMI: Ubuntu 22.04 LTS
- Type: t3.medium (minimum)
- Stockage: 30GB SSD

**2. Configurer RDS PostgreSQL**
- Engine: PostgreSQL 14
- Instance: db.t3.micro (dev) ou db.t3.small (prod)
- Stockage: 20GB

**3. Configurer ElastiCache Redis**
- Engine: Redis 7.x
- Node type: cache.t3.micro

**4. Suivre les étapes VPS ci-dessus**
- Utiliser les endpoints RDS et ElastiCache dans .env

#### Google Cloud Platform

**1. Compute Engine**
```bash
gcloud compute instances create eduai-backend \
    --machine-type=e2-medium \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB
```

**2. Cloud SQL PostgreSQL**
```bash
gcloud sql instances create eduai-db \
    --database-version=POSTGRES_14 \
    --tier=db-f1-micro \
    --region=us-central1
```

**3. Memorystore Redis**
```bash
gcloud redis instances create eduai-redis \
    --size=1 \
    --region=us-central1
```

---

### 5. Déploiement avec Kubernetes

**Fichier: k8s/deployment.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eduai-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: eduai-api
  template:
    metadata:
      labels:
        app: eduai-api
    spec:
      containers:
      - name: api
        image: eduai/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: eduai-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: eduai-secrets
              key: redis-url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: eduai-secrets
              key: openai-key
---
apiVersion: v1
kind: Service
metadata:
  name: eduai-api-service
spec:
  selector:
    app: eduai-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## 🔒 Checklist de Sécurité Production

- [ ] Changer SECRET_KEY (générer aléatoirement)
- [ ] Utiliser des mots de passe forts pour PostgreSQL
- [ ] Configurer ALLOWED_ORIGINS strictement
- [ ] Activer HTTPS (Let's Encrypt)
- [ ] Configurer le firewall (UFW/iptables)
- [ ] Désactiver DEBUG=false
- [ ] Limiter l'accès SSH (clés uniquement)
- [ ] Configurer fail2ban
- [ ] Sauvegardes automatiques de la base de données
- [ ] Monitoring et alertes
- [ ] Logs centralisés
- [ ] Rate limiting sur tous les endpoints

---

## 📊 Monitoring et Logs

### Logs Application

```bash
# Logs FastAPI
tail -f /home/eduai/eduai-backend/logs/api.log

# Logs Celery
tail -f /home/eduai/eduai-backend/logs/celery.log

# Logs Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Monitoring avec Prometheus + Grafana

**Installation:**
```bash
# Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Grafana
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
sudo apt-get update
sudo apt-get install grafana
```

---

## 🔄 Mises à Jour

### Mise à jour de l'application

```bash
cd /home/eduai/eduai-backend
git pull origin main

source venv/bin/activate
pip install -r requirements.txt

# Appliquer les migrations
alembic upgrade head

# Redémarrer les services
sudo supervisorctl restart eduai-api
sudo supervisorctl restart eduai-celery
```

---

## 💾 Sauvegardes

### Sauvegarde PostgreSQL

```bash
# Script de sauvegarde
sudo nano /home/eduai/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/eduai/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
pg_dump -U eduai eduai > $BACKUP_DIR/eduai_$DATE.sql

# Backup uploads et chroma_db
tar -czf $BACKUP_DIR/files_$DATE.tar.gz \
    /home/eduai/eduai-backend/uploads \
    /home/eduai/eduai-backend/chroma_db

# Garder seulement les 7 derniers jours
find $BACKUP_DIR -type f -mtime +7 -delete
```

```bash
chmod +x /home/eduai/backup.sh

# Cron pour sauvegarde quotidienne à 2h du matin
crontab -e
0 2 * * * /home/eduai/backup.sh
```

---

## 🆘 Dépannage Production

### Service ne démarre pas

```bash
# Vérifier les logs
sudo supervisorctl tail -f eduai-api stderr
sudo supervisorctl tail -f eduai-celery stderr

# Vérifier la configuration
source venv/bin/activate
python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

### Problèmes de performance

```bash
# Vérifier l'utilisation des ressources
htop

# Vérifier PostgreSQL
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"

# Vérifier Redis
redis-cli INFO
```

### Erreurs 502 Bad Gateway

```bash
# Vérifier que l'API tourne
curl http://localhost:8000/health

# Vérifier Nginx
sudo nginx -t
sudo systemctl status nginx
```

---

## 📞 Support

Pour toute question sur le déploiement:
1. Vérifier les logs
2. Consulter cette documentation
3. Vérifier la configuration .env
4. Tester en local d'abord

---

**Bon déploiement ! 🚀**
