# Step 5: Docker & CI/CD Setup Guide

This guide covers setting up Docker containers and CI/CD pipelines for the Image Processing API project.

## Table of Contents

1. [Docker Setup](#docker-setup)
2. [Docker Compose Configuration](#docker-compose-configuration)
3. [CI/CD Pipeline Setup](#cicd-pipeline-setup)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Strategies](#deployment-strategies)
6. [Monitoring and Health Checks](#monitoring-and-health-checks)
7. [Security Considerations](#security-considerations)

---

## Docker Setup

### Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads && \
    chmod 755 uploads

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')"

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Backend .dockerignore

Create `backend/.dockerignore`:

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.env
.venv
venv/
ENV/
env/
*.db
*.sqlite
*.sqlite3
uploads/*
!uploads/.gitkeep
.git
.gitignore
README.md
.pytest_cache
.coverage
htmlcov/
.mypy_cache
.dockerignore
Dockerfile
docker-compose.yml
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
# Multi-stage build for smaller final image

# Stage 1: Build
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source files
COPY . .

# Build the application (if using a build step)
# RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Copy built files from builder
COPY --from=builder /app /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

### Frontend nginx.conf

Create `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Serve static files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API proxy (if needed)
    location /api {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Frontend .dockerignore

Create `frontend/.dockerignore`:

```
node_modules
npm-debug.log
.git
.gitignore
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
.DS_Store
*.log
coverage
.nyc_output
dist
build
.dockerignore
Dockerfile
docker-compose.yml
```

---

## Docker Compose Configuration

Create `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  # Backend API Service
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: image-processing-api
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=sqlite:///./image_processing.db
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
      - CORS_ORIGINS=http://localhost:3000,http://localhost:80
      - MAX_UPLOAD_SIZE_MB=10
      - ALLOWED_IMAGE_TYPES=jpg,jpeg,png,gif,webp
      - RATE_LIMIT_PER_MINUTE=60
      - LOG_LEVEL=INFO
    volumes:
      - ./backend/uploads:/app/uploads
      - ./backend/image_processing.db:/app/image_processing.db
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    depends_on:
      - db

  # Frontend Service
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: image-processing-frontend
    ports:
      - "3000:80"
    environment:
      - API_BASE_URL=http://localhost:8001
    networks:
      - app-network
    restart: unless-stopped
    depends_on:
      - backend

  # Database Service (Optional - for PostgreSQL)
  db:
    image: postgres:15-alpine
    container_name: image-processing-db
    environment:
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-postgres}
      - POSTGRES_DB=${DB_NAME:-image_processing}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Nginx Reverse Proxy (Optional - for production)
  nginx:
    image: nginx:alpine
    container_name: image-processing-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    networks:
      - app-network
    restart: unless-stopped
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:

networks:
  app-network:
    driver: bridge
```

### Docker Compose Override for Development

Create `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  backend:
    volumes:
      - ./backend:/app
    environment:
      - LOG_LEVEL=DEBUG
    command: uvicorn app:app --host 0.0.0.0 --port 8001 --reload

  frontend:
    volumes:
      - ./frontend:/usr/share/nginx/html
```

---

## CI/CD Pipeline Setup

### GitHub Actions Workflow

Create `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Lint and Test
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        working-directory: ./backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run linter
        working-directory: ./backend
        run: |
          pip install flake8 black isort
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
          black --check .
          isort --check-only .

      - name: Run tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost:5432/test_db
          SECRET_KEY: test-secret-key
        run: |
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  # Build and Push Docker Images
  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta-backend
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-backend
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push backend
        uses: docker/build-push-action@v4
        with:
          context: ./backend
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta-backend.outputs.tags }}
          labels: ${{ steps.meta-backend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Extract metadata
        id: meta-frontend
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-frontend
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push frontend
        uses: docker/build-push-action@v4
        with:
          context: ./frontend
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Deploy to Staging
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment:
      name: staging
      url: https://staging.example.com

    steps:
      - uses: actions/checkout@v3

      - name: Deploy to staging
        run: |
          echo "Deploying to staging environment"
          # Add your deployment commands here
          # e.g., SSH into server, pull images, restart containers

  # Deploy to Production
  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://example.com

    steps:
      - uses: actions/checkout@v3

      - name: Deploy to production
        run: |
          echo "Deploying to production environment"
          # Add your deployment commands here
```

### GitLab CI/CD Pipeline

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

# Test Stage
test:backend:
  stage: test
  image: python:3.11-slim
  services:
    - postgres:15-alpine
  variables:
    POSTGRES_DB: test_db
    POSTGRES_USER: test_user
    POSTGRES_PASSWORD: test_password
    DATABASE_URL: postgresql://test_user:test_password@postgres:5432/test_db
  before_script:
    - cd backend
    - pip install -r requirements.txt
    - pip install pytest pytest-cov
  script:
    - pytest --cov=app --cov-report=xml
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: backend/coverage.xml

# Build Stage
build:backend:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - cd backend
    - docker build -t $CI_REGISTRY_IMAGE/backend:$CI_COMMIT_SHORT_SHA -t $CI_REGISTRY_IMAGE/backend:latest .
    - docker push $CI_REGISTRY_IMAGE/backend:$CI_COMMIT_SHORT_SHA
    - docker push $CI_REGISTRY_IMAGE/backend:latest
  only:
    - main
    - develop

build:frontend:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - cd frontend
    - docker build -t $CI_REGISTRY_IMAGE/frontend:$CI_COMMIT_SHORT_SHA -t $CI_REGISTRY_IMAGE/frontend:latest .
    - docker push $CI_REGISTRY_IMAGE/frontend:$CI_COMMIT_SHORT_SHA
    - docker push $CI_REGISTRY_IMAGE/frontend:latest
  only:
    - main
    - develop

# Deploy Stage
deploy:staging:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
  script:
    - ssh $STAGING_SERVER "cd /opt/app && docker-compose pull && docker-compose up -d"
  environment:
    name: staging
    url: https://staging.example.com
  only:
    - develop

deploy:production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
  script:
    - ssh $PRODUCTION_SERVER "cd /opt/app && docker-compose pull && docker-compose up -d"
  environment:
    name: production
    url: https://example.com
  when: manual
  only:
    - main
```

---

## Environment Configuration

### Production Environment Variables

Create `backend/.env.production`:

```bash
# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@db:5432/image_processing

# File Upload
MAX_UPLOAD_SIZE_MB=10
ALLOWED_IMAGE_TYPES=jpg,jpeg,png,gif,webp

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
```

### Docker Secrets Management

For sensitive data, use Docker secrets:

```yaml
services:
  backend:
    secrets:
      - db_password
      - secret_key
    environment:
      - DATABASE_URL=postgresql://user:${DB_PASSWORD}@db:5432/image_processing
      - SECRET_KEY_FILE=/run/secrets/secret_key

secrets:
  db_password:
    external: true
  secret_key:
    file: ./secrets/secret_key.txt
```

---

## Deployment Strategies

### Blue-Green Deployment

```yaml
# docker-compose.blue.yml
services:
  backend-blue:
    image: your-registry/backend:latest
    # ... configuration

# docker-compose.green.yml
services:
  backend-green:
    image: your-registry/backend:latest
    # ... configuration
```

### Rolling Updates

```bash
# Update service with zero downtime
docker-compose up -d --no-deps --build backend
```

### Health Check Script

Create `scripts/health-check.sh`:

```bash
#!/bin/bash

MAX_RETRIES=30
RETRY_INTERVAL=2
HEALTH_ENDPOINT="http://localhost:8001/health"

for i in $(seq 1 $MAX_RETRIES); do
    if curl -f $HEALTH_ENDPOINT > /dev/null 2>&1; then
        echo "Health check passed"
        exit 0
    fi
    echo "Health check failed, retrying... ($i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

echo "Health check failed after $MAX_RETRIES attempts"
exit 1
```

---

## Monitoring and Health Checks

### Prometheus Metrics (Optional)

Add to `backend/app.py`:

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

### Docker Health Checks

Already included in Dockerfiles, but can be customized:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Security Considerations

### 1. Use Non-Root User

Already implemented in Dockerfiles with `USER appuser`.

### 2. Scan Images for Vulnerabilities

```bash
# Using Trivy
trivy image your-registry/backend:latest

# Using Docker Scout
docker scout cves your-registry/backend:latest
```

### 3. Secrets Management

- Use Docker secrets or external secret managers (AWS Secrets Manager, HashiCorp Vault)
- Never commit secrets to version control
- Rotate secrets regularly

### 4. Network Security

```yaml
networks:
  app-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 5. Resource Limits

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## Quick Start Commands

### Development

```bash
# Build and start services
docker-compose up --build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Production

```bash
# Build for production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Update services
docker-compose pull
docker-compose up -d

# Backup database
docker-compose exec db pg_dump -U postgres image_processing > backup.sql
```

---

## Troubleshooting

### Common Issues

1. **Port already in use**: Change port mappings in `docker-compose.yml`
2. **Permission denied**: Check file permissions and user in Dockerfile
3. **Database connection failed**: Verify DATABASE_URL and network connectivity
4. **Build cache issues**: Use `docker-compose build --no-cache`

### Debug Commands

```bash
# Inspect container
docker-compose exec backend sh

# Check logs
docker-compose logs backend

# Check network
docker network inspect generated_project_f06bb423_app-network

# Check volumes
docker volume ls
```

---

## Next Steps

1. Set up container registry (Docker Hub, GitHub Container Registry, or AWS ECR)
2. Configure CI/CD secrets and environment variables
3. Set up monitoring and alerting (Prometheus, Grafana)
4. Implement backup strategies for database
5. Set up SSL/TLS certificates for production
6. Configure domain and DNS settings
7. Set up log aggregation (ELK stack, Loki)

---

## Additional Resources

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)

