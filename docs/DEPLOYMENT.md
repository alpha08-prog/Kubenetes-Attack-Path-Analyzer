# Deployment Guide

> Comprehensive guide to deploying Attack Path Analyzer in various environments

---

## Table of Contents

1. [Docker Deployment (Recommended)](#docker-deployment-recommended)
2. [Local Development Setup](#local-development-setup)
3. [Kubernetes Deployment](#kubernetes-deployment-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Troubleshooting](#troubleshooting)

---

## Docker Deployment (Recommended)

### Prerequisites

- Docker Desktop (or Docker Engine)
- Docker Compose 2.0+
- Git

### Quickstart (One Command)

```bash
git clone https://github.com/your-team/attack-path-analyzer.git
cd attack-path-analyzer
make demo
```

Opens:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

### Manual Docker Compose

**1. Create `.env` file:**
```bash
cp .env.example .env
```

**2. Edit `.env`:**
```env
GEMINI_API_KEY=your_key_here
MOCK_MODE=true
CLUSTER_NAME=demo-cluster
DEBUG=false
```

**3. Start containers:**
```bash
docker-compose up --build
```

**4. Verify health:**
```bash
curl http://localhost:8000/health
# Output: {"status": "healthy", ...}
```

### Docker Compose File Structure

```yaml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: docker/backend.Dockerfile
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - MOCK_MODE=${MOCK_MODE:-true}
    volumes:
      - ./docs:/app/docs

  frontend:
    build:
      context: frontend
      dockerfile: ../docker/frontend.Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - backend

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend
      - frontend
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes (for AI features) | N/A | Free key from [aistudio.google.com](https://aistudio.google.com) |
| `MOCK_MODE` | No | `true` | Use mock data vs. live kubectl |
| `CLUSTER_NAME` | No | `default-cluster` | Display name in reports |
| `DEBUG` | No | `false` | Verbose logging |
| `DATABASE_URL` | No | `sqlite:///./history.db` | History storage (SQLite by default) |

---

## Local Development Setup

### Option A: Python Virtual Environment

**1. Prerequisites:**
```bash
# Check Python version
python --version  # Must be 3.10+

# Check pip
pip --version
```

**2. Setup backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Mac/Linux
# or: venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

**3. Start backend (with hot reload):**
```bash
python -m uvicorn app.main:app --reload --port 8000
```

**4. In another terminal, setup frontend:**
```bash
cd frontend
npm install
npm run dev
```

**5. Access:**
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

### Option B: Make Commands

```bash
# Install dependencies
make install

# Start backend with hot reload
make dev-backend

# Start frontend with hot reload
make dev-frontend

# Run in parallel (requires tmux or terminal multiplexer)
make dev
```

---

## Kubernetes Deployment

### Helm Chart Structure

```
deployment/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── ingress.yaml
```

### Installation

```bash
# Add helm repo (if applicable)
helm repo add your-team https://charts.example.com

# Install release
helm install attack-path-analyzer your-team/attack-path-analyzer \
  --namespace security \
  --values deployment/values.yaml
```

### values.yaml Example

```yaml
replicaCount: 2

image:
  repository: your-registry/attack-path-analyzer
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  host: analyzer.example.com
  tls:
    enabled: true

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

env:
  MOCK_MODE: "false"
  CLUSTER_NAME: "production"

# Persistent storage for graph data
persistence:
  enabled: true
  size: 10Gi
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace security

# Deploy using Helm
helm install attack-path-analyzer ./deployment \
  -n security

# Verify deployment
kubectl get pods -n security
kubectl logs -n security <pod-name>

# Port forward for testing
kubectl port-forward -n security svc/attack-path-analyzer 8000:8000
```

---

## Environment Configuration

### Configuration Priority

```
1. Environment variables (highest priority)
2. .env file
3. config.py defaults (lowest priority)
```

### config.py Structure

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Data Settings
    mock_mode: bool = True
    cluster_name: str = "default-cluster"

    # AI Settings
    gemini_api_key: str = ""
    gemini_timeout: int = 30

    # Database
    database_url: str = "sqlite:///./history.db"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### Loading Configuration

```python
# backend/app/main.py
from app.config import settings

app.title = f"Attack Path Analyzer - {settings.cluster_name}"
print(f"Mode: {'MOCK' if settings.mock_mode else 'LIVE'}")
```

---

## Database Setup

### SQLite (Default)

```bash
# Automatic on first run
# Creates: history.db in project root

# Backup
sqlite3 history.db ".backup history-backup.db"
```

### PostgreSQL (Production)

**1. Update `.env`:**
```env
DATABASE_URL=postgresql://user:password@localhost:5432/analyzer
```

**2. Install driver:**
```bash
pip install psycopg2-binary
```

**3. Run migrations:**
```bash
alembic upgrade head
```

### MySQL/MariaDB

**1. Update `.env`:**
```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/analyzer
```

**2. Install driver:**
```bash
pip install pymysql
```

---

## Performance Tuning

### For Large Graphs (> 500 nodes)

**1. Increase memory limits:**
```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - PYTHONUNBUFFERED=1
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

**2. Enable result caching:**
```python
# backend/app/main.py
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend

FastAPICache2.init(RedisBackend(url="redis://localhost"), prefix="fastapi-cache")
```

**3. Approximate algorithms for centrality:**
```python
# backend/app/algorithm/centrality.py
nx.betweenness_centrality(G, k=100)  # Sample 100 nodes instead of all
```

### Load Testing

```bash
# Install load testing tool
pip install locust

# Run load test
locust -f locustfile.py --host=http://localhost:8000

# Or use Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/graph/summary
```

---

## Monitoring & Logging

### Logging Configuration

```python
# backend/app/utils/logger.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

### Enable Debug Logging

```env
DEBUG=true
```

### View Logs

```bash
# Docker logs
docker-compose logs -f backend

# Kubernetes logs
kubectl logs -n security <pod-name> -f

# Local logs
tail -f app.log
```

### Health Checks

```bash
# Endpoint
curl http://localhost:8000/health

# Docker health check
docker inspect <container-id> | grep Health
```

---

## Backup & Recovery

### Backup Strategy

```bash
# Backup everything
docker-compose exec backend tar czf /tmp/backup.tar.gz /app/docs /app/history.db
docker cp <container-id>:/tmp/backup.tar.gz ./backup.tar.gz

# Restore
docker cp ./backup.tar.gz <container-id>:/tmp/
docker-compose exec backend tar xzf /tmp/backup.tar.gz -C /app
```

### Graph Data Backup

```bash
# Backup cluster-graph.json
cp docs/mock-cluster-graph.json docs/mock-cluster-graph.json.backup

# Backup history
sqlite3 history.db ".dump" > history-export.sql
```

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose logs backend
# Look for: error, traceback, module not found
```

**Common causes:**
- Missing `.env` file: `cp .env.example .env`
- Invalid GEMINI_API_KEY: Check [aistudio.google.com](https://aistudio.google.com)
- Port already in use: `lsof -i :8000`

### API Returning 500 Errors

```bash
# Check backend logs
docker-compose logs -f backend

# Verify graph loaded
curl http://localhost:8000/api/graph/summary

# Reload graph
curl -X POST http://localhost:8000/api/graph/reload
```

### High Memory Usage

```bash
# Check container memory
docker stats

# Reduce graph size (if possible)
# Or enable approximate algorithms (see Performance Tuning)
```

### Network Issues

```bash
# Frontend can't reach backend?
# Check if services are on same network
docker network ls
docker network inspect <network-name>

# Or use environment variable
REACT_APP_API_URL=http://backend:8000
```

---

## Security Best Practices

### 1. API Authentication (Production)

```python
# backend/app/main.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    if not verify_jwt_token(credentials.credentials):
        raise HTTPException(status_code=401)
    return credentials.credentials
```

### 2. HTTPS/TLS

```yaml
# docker-compose.yml
services:
  nginx:
    ports:
      - "443:443"
    volumes:
      - ./certs:/etc/nginx/certs
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
```

### 3. CORS Configuration

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Production origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. Environment Secrets

```bash
# NEVER commit .env file
echo ".env" >> .gitignore

# Use secrets management (production)
# - Docker Secrets (Swarm)
# - Kubernetes Secrets
# - Vault
# - AWS Secrets Manager
```

---

## Upgrading

### Backup First

```bash
# Save current state
docker-compose down
cp docs/mock-cluster-graph.json docs/mock-cluster-graph.json.backup
tar czf backup-$(date +%Y%m%d).tar.gz docs history.db
```

### Update Code

```bash
git pull origin main
```

### Rebuild & Restart

```bash
docker-compose up --build -d
docker-compose logs -f backend
```

### Database Migrations (if applicable)

```bash
docker-compose exec backend alembic upgrade head
```

---

## See Also
- [README.md](../README.md) — Quick start
- [QUICK_START.md](QUICK_START.md) — 5-minute setup
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [Environment Configuration](#environment-configuration) — Config reference
