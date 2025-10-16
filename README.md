# 🎬 Movie-Streaming-API

A modern backend for an **online movie platform** where users can register, browse, purchase, and watch films — all via a fully featured REST API.  
Built with using **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, and **Stripe**.

## 🧩 Overview

The API automates user management, payments, and content control.  
It replaces manual handling of movie catalogs and payments with a **scalable, secure, and fully automated system**.

Features:
* Email registration & activation (valid for 24h)
* JWT authentication (Access & Refresh)
* Password reset via email
* Role system: User / Moderator / Admin
* Full movie catalog with filtering, rating & favorites
* Shopping cart & order management
* Stripe payments
* Async tasks (emails, cleanup) via Celery
* Swagger & Redoc documentation

## 🚀 Tech Stack

* Python 3.11
* FastAPI
* PostgreSQL
* Redis + Celery + Celery Beat
* MinIO
* JWT (access & refresh)
* Stripe API
* Poetry
* Docker + Docker Compose
* GitHub Actions
* Pytest
* Swagger / Redoc

## ⚙️ Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Artcrafterrra/movie-streaming-api.git
cd movie-streaming-api
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
poetry install
cp .env.example .env
alembic upgrade head
uvicorn src.main:app --reload
celery -A src.celery_app.celery worker --loglevel=info
celery -A src.celery_app.celery beat --loglevel=info
```

Now your API is available at:
Swagger Docs → http://localhost:8000/docs
Redoc → http://localhost:8000/redoc

### 🐳 Docker setup
```bash
docker-compose up --build
```
### Docker-compose
```bash
docker-compose -f docker-compose-dev.yml up --build # Development
docker-compose -f docker-compose-prod.yml up --build # Production
docker-compose -f docker-compose-tests.yml up --build # Tests
```

### Initialize database (optional)
```bash
psql -U postgres -d movie_db -f init.sql
```
### Run tests
```bash
pytest -v
```
## 🔐 Authentication
Use these tokens in headers:


## DB Scheme
![img.png](img.png)
