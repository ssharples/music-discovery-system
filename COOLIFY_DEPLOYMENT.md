# 🚀 Coolify VPS Deployment Guide - Music Discovery System

This guide will walk you through deploying your music discovery system on Coolify VPS.

## 📋 Prerequisites

### What You Need
- ✅ Coolify instance running on your VPS
- ✅ GitHub repository with your code
- ✅ Domain name (optional but recommended)
- ✅ API keys for all services

### Required API Keys
- **DeepSeek API Key** - [Get from DeepSeek Platform](https://platform.deepseek.com/api_keys)
- **YouTube Data API v3** - [Google Cloud Console](https://console.cloud.google.com/)
- **Spotify API** - [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- **Supabase** - [Supabase Dashboard](https://supabase.com/dashboard)
- **Firecrawl API** (optional) - [Firecrawl.dev](https://firecrawl.dev)

## 🚀 Step-by-Step Deployment

### Step 1: Prepare Your Repository

1. **Push all changes to GitHub:**
   ```bash
   git add .
   git commit -m "feat: add Coolify deployment configuration"
   git push origin main
   ```

2. **Verify required files are present:**
   - ✅ `Dockerfile` (root level)
   - ✅ `docker-compose.coolify.yml`
   - ✅ `deployment/nginx.conf`
   - ✅ `deployment/supervisord.conf`
   - ✅ `.dockerignore`

### Step 2: Set Up Supabase Database

1. **Go to your Supabase project**
2. **Navigate to SQL Editor**
3. **Run the database schema:**
   ```sql
   -- Copy and paste the contents from your database-schema file
   ```

### Step 3: Create New Application in Coolify

1. **Login to your Coolify dashboard**
2. **Click "New Application"**
3. **Choose "Docker Compose"**
4. **Configure the application:**
   - **Name**: `music-discovery-system`
   - **Git Repository**: Your GitHub repo URL
   - **Branch**: `main`
   - **Docker Compose File**: `docker-compose.coolify.yml` (or `docker-compose.coolify-alt.yml` if port 8000 conflicts)

### Step 4: Configure Environment Variables

In Coolify, add these environment variables:

#### **Required API Keys:**
```bash
# DeepSeek AI
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# YouTube API
YOUTUBE_API_KEY=your_youtube_api_key_here

# Spotify API
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Optional: Firecrawl
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
```

#### **Security & Configuration:**
```bash
# Security
SECRET_KEY=your_super_secure_random_secret_key_here

# CORS (replace with your domain)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Optional: Error Tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

#### **How to Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 5: Configure Domain (Optional)

1. **In Coolify, go to your application**
2. **Click "Domains"**
3. **Add your domain**: `yourdomain.com`
4. **Enable SSL**: Coolify will auto-generate Let's Encrypt certificate

### Step 6: Deploy

1. **Click "Deploy" in Coolify**
2. **Monitor the build logs**
3. **Wait for deployment to complete** (usually 3-5 minutes)

### Step 7: Verify Deployment

1. **Check application status**: Should show "Running"
2. **Visit your domain** or Coolify-provided URL
3. **Test the API**: `https://yourdomain.com/api/health`
4. **Check logs** if needed: Click "Logs" in Coolify

## ⚠️ **Port Conflict Resolution**

**If your Coolify dashboard uses port 8000:**
- Use `docker-compose.coolify-alt.yml` instead
- Your app will be accessible on:
  - **Frontend**: Port 80 (standard web traffic)
  - **API**: Port 3001 (instead of 8000)
  - **Health check**: `http://yourdomain.com/health`

**No changes needed to your application code** - only the external port mapping changes.

## 🔧 Configuration Details

### Dockerfile Architecture
The deployment uses a multi-stage build:
- **Stage 1**: Builds React frontend
- **Stage 2**: Sets up Python backend + Nginx + Redis
- **Supervisor**: Manages all processes

### Services Running
- **Nginx** (Port 80): Serves frontend + proxies API
- **FastAPI Backend** (Port 8000): Python API server
- **Redis**: In-memory caching and task queue

### Health Monitoring
- **Health endpoint**: `/health`
- **Automatic restarts**: If any service fails
- **Log aggregation**: All logs in Coolify dashboard

## 🛠️ Troubleshooting

### Common Issues

#### ❌ Build Fails
```bash
# Check build logs in Coolify
# Common causes:
- Missing environment variables
- API key format issues
- Network connectivity during build
```

#### ❌ Application Won't Start
```bash
# Check application logs in Coolify
# Common causes:
- Invalid Supabase URL/keys
- Missing required environment variables
- Port conflicts
```

#### ❌ API Returns 500 Errors
```bash
# Check backend logs specifically
# Common causes:
- Database connection issues
- Invalid API keys
- Missing Redis connection
```

### Quick Fixes

#### **Reset Application:**
```bash
# In Coolify:
1. Stop application
2. Clear build cache
3. Redeploy
```

#### **Update Environment Variables:**
```bash
# In Coolify:
1. Go to Environment Variables
2. Update values
3. Restart application
```

#### **Check Service Status:**
```bash
# SSH into your VPS and run:
docker ps | grep music-discovery
docker logs <container-id>
```

## 📈 Post-Deployment

### Performance Optimization
- **Monitor CPU/Memory** usage in Coolify
- **Scale horizontally** if needed (add more containers)
- **Enable CDN** for static assets

### Security
- **Regular updates**: Keep dependencies updated
- **SSL certificate**: Auto-renewed by Coolify
- **Firewall**: Ensure only necessary ports are open

### Monitoring
- **Application logs**: Available in Coolify dashboard
- **Error tracking**: If Sentry is configured
- **Uptime monitoring**: Consider external services

## 🎯 Success Checklist

After deployment, verify:
- ✅ Frontend loads at your domain
- ✅ API health check returns 200: `/api/health`
- ✅ Can search for artists
- ✅ Database connections work
- ✅ All environment variables are set
- ✅ SSL certificate is active (if domain configured)

## 🆘 Getting Help

If you encounter issues:
1. **Check Coolify logs** first
2. **Verify environment variables** are correctly set
3. **Test API endpoints** individually
4. **Check database connectivity** in Supabase dashboard

Your music discovery system should now be live and accessible! 🎉 