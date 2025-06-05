# 🚀 Music Discovery System - Deployment Guide

This guide covers deployment options for the Music Discovery System, from local development to production environments.

## 📋 Prerequisites

### Required Software
- **Docker** (v20.10+) and **Docker Compose** (v2.0+)
- **Node.js** (v18+) and **npm** (v8+)
- **Python** (v3.11+) and **pip**
- **Git**

### Required Services
- **Supabase** account and project
- **YouTube Data API v3** key
- **Spotify API** credentials
- **DeepSeek API** key
- **Firecrawl API** key (optional)

## 🛠️ Quick Start

### 1. Automated Setup (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd music-discovery-system

# Run the setup script
./setup.sh
```

The setup script will guide you through:
- Environment configuration
- Database setup
- Backend and frontend installation
- Development environment startup

### 2. Manual Setup

#### Environment Configuration
```bash
# Copy environment template
cp env.example .env

# Edit with your API keys
nano .env
```

#### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

#### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

#### Database Setup
1. Go to your Supabase dashboard
2. Navigate to SQL Editor
3. Run the contents of `database-schema` file

## 🏗️ Development Environment

### Start Development Services
```bash
# Option 1: Using setup script
./setup.sh
# Choose option 4: "Start Development Environment"

# Option 2: Manual start
docker-compose up -d redis
cd backend && source venv/bin/activate && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

### Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Redis**: localhost:6379

## 🌐 Production Deployment

### Docker Compose Production

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Environment Variables for Production

Create a production `.env` file with:

```bash
# Production overrides
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://yourdomain.com

# Security
SECRET_KEY=your_super_secure_secret_key_here
REDIS_PASSWORD=your_redis_password

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
GRAFANA_PASSWORD=your_grafana_admin_password
```

### Production Services

After deployment, access:
- **Application**: http://localhost (or your domain)
- **Prometheus Monitoring**: http://localhost:9090
- **Grafana Dashboards**: http://localhost:3001

## 🔧 Troubleshooting

### Common Issues

#### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common fixes
- Verify all environment variables are set
- Check database connectivity
- Ensure Redis is running
```

#### Frontend build fails
```bash
# Check Node.js version
node --version  # Should be 18+

# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

#### Database connection issues
```bash
# Test Supabase connection
curl -H "apikey: YOUR_SUPABASE_KEY" \
     -H "Authorization: Bearer YOUR_SUPABASE_KEY" \
     "YOUR_SUPABASE_URL/rest/v1/artists?select=count"
```

### Performance Optimization

#### Backend
- Enable Redis caching
- Use connection pooling
- Implement rate limiting
- Optimize database queries

#### Frontend
- Enable gzip compression
- Use CDN for static assets
- Implement code splitting
- Optimize images

## 📈 Scaling

### Horizontal Scaling

#### Backend
```yaml
# docker-compose.prod.yml
backend:
  deploy:
    replicas: 3
  # Add load balancer
```

#### Database
- Use read replicas
- Implement connection pooling
- Consider database sharding

#### Caching
- Redis Cluster for high availability
- Implement multi-level caching
- Use CDN for static content

### Monitoring Scaling

Set up alerts for:
- High CPU/Memory usage
- Database connection limits
- API response times
- Error rates

## 🆘 Support

For deployment issues:
1. Check the troubleshooting section
2. Review logs: `docker-compose logs`
3. Verify environment configuration
4. Check service health endpoints

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [React Deployment](https://create-react-app.dev/docs/deployment/) 