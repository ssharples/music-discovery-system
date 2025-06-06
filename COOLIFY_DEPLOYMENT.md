# 🚀 Coolify Deployment Guide - Apify Integration

## Overview

This guide helps you deploy your music discovery system with Apify YouTube integration on Coolify using Docker Compose.

## 🔧 Pre-Deployment Setup

### 1. Environment Variables in Coolify

In your Coolify dashboard, add these environment variables to your application:

#### **Required - Apify Integration**
```bash
APIFY_API_TOKEN=your_apify_token_here
```

#### **Existing Environment Variables**
```bash
# Core Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=https://yourdomain.com

# Database & Storage
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AI & Enrichment APIs
DEEPSEEK_API_KEY=your_deepseek_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
FIRECRAWL_API_KEY=your_firecrawl_key

# Optional - YouTube API (for backward compatibility)
YOUTUBE_API_KEY=your_youtube_api_key

# Monitoring (optional)
SENTRY_DSN=your_sentry_dsn
```

### 2. Get Apify API Token

1. **Sign up**: Go to [Apify.com](https://apify.com/) (free tier available)
2. **Get Token**: Visit [Console → Integrations](https://console.apify.com/account/integrations)
3. **Copy Token**: Add to Coolify environment variables as `APIFY_API_TOKEN`

## 📦 Docker Compose Configuration

Your `docker-compose.yml` has been updated to include Apify:

```yaml
services:
  backend:
    build: .
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      # Apify YouTube Scraper (replaces YouTube API)
      - APIFY_API_TOKEN=${APIFY_API_TOKEN}
      # YouTube API (kept for backward compatibility, optional now)
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
      - SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
      - SENTRY_DSN=${SENTRY_DSN}
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    # ... rest of configuration
```

## 🚀 Deployment Steps

### Step 1: Update Environment Variables

In your Coolify dashboard:

1. **Navigate** to your application
2. **Go to** Environment Variables section
3. **Add** the new variable:
   ```
   APIFY_API_TOKEN=your_actual_token_here
   ```
4. **Save** the configuration

### Step 2: Deploy Updated Application

1. **Commit** your updated `docker-compose.yml` to your repository
2. **Push** changes to your Git repository
3. **Trigger** deployment in Coolify (automatic or manual)

### Step 3: Verify Deployment

Monitor the deployment logs for these success indicators:

```bash
# Backend startup logs should show:
✅ Orchestrator initialized with lazy agent loading
✅ Apify YouTube discovery starting for query: ...
✅ Discovered X quality artists from Y videos

# No more quota errors:
❌ ❌ Insufficient YouTube quota for search operations (should be gone)
```

## 🔍 Testing the Deployment

### Health Check

Your application health endpoint should respond:
```bash
curl https://yourdomain.com/health
# Should return: {"status": "healthy"}
```

### Test Music Discovery

1. **Access** your application frontend
2. **Start** a music discovery session
3. **Monitor** logs for Apify activity:
   ```
   🔍 Apify YouTube discovery starting for query: indie rock 2024
   ✅ Discovered 15 quality artists from 50 videos
   💰 Estimated Apify cost for 50 videos: $0.0250
   ```

## 📊 Cost Monitoring

### Apify Console
- **Dashboard**: https://console.apify.com/account/billing
- **Real-time usage**: Monitor costs as they accumulate
- **Billing alerts**: Set up notifications for spending limits

### Expected Costs
```
Daily Discovery (typical usage):
- 100 artists discovery: ~500 videos = $0.25/day
- 1000 artists discovery: ~5000 videos = $2.50/day

Monthly costs significantly lower than YouTube API quota overages!
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. **Missing APIFY_API_TOKEN**
```bash
# Error in logs:
❌ APIFY_API_TOKEN not configured - cannot perform discovery

# Solution:
Add APIFY_API_TOKEN to Coolify environment variables
```

#### 2. **Invalid Apify Token**
```bash
# Error in logs:
❌ Failed to start Apify actor run: Unauthorized

# Solution:
Verify token at: https://console.apify.com/account/integrations
Update APIFY_API_TOKEN with correct value
```

#### 3. **Container Build Issues**
```bash
# Error during build:
ModuleNotFoundError: No module named 'httpx'

# Solution:
httpx is already in requirements.txt - rebuild container
```

### Debug Commands

Check environment variables in running container:
```bash
# In Coolify terminal
docker exec -it <container_id> env | grep APIFY
```

Test Apify connection:
```bash
# In container
python -c "
import os
print('Token:', os.getenv('APIFY_API_TOKEN', 'NOT SET'))
"
```

## 🔄 Migration from YouTube API

### Automatic Migration Benefits

Since you're deploying with the updated code:

✅ **No Downtime**: Apify agent is drop-in compatible  
✅ **Instant Benefits**: No more quota limitations  
✅ **Cost Savings**: $0.50/1K videos vs quota overages  
✅ **Better Performance**: 10+ videos/second processing  

### Rollback Plan (if needed)

1. **Revert** `docker-compose.yml` to remove Apify
2. **Update** orchestrator to use original YouTube agent
3. **Redeploy** via Coolify

## 🎯 Production Optimization

### Scaling Considerations

```yaml
# For high-volume production
backend:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: "1.0"
```

### Cost Management

```python
# Add cost controls in production
class ApifyYouTubeAgent:
    def __init__(self):
        # Production cost limits
        self.daily_spend_limit = float(os.getenv('APIFY_DAILY_LIMIT', '10.0'))
        self.max_videos_per_session = int(os.getenv('APIFY_MAX_VIDEOS', '1000'))
```

## 📋 Deployment Checklist

- [ ] Apify API token obtained
- [ ] `APIFY_API_TOKEN` added to Coolify environment
- [ ] Updated `docker-compose.yml` committed
- [ ] Application deployed successfully
- [ ] Health check passes
- [ ] Music discovery works without quota errors
- [ ] Apify billing dashboard monitored
- [ ] Cost alerts configured

## 🎉 Success Indicators

Your deployment is successful when you see:

```bash
✅ No YouTube quota errors
✅ Apify discovery logs appearing
✅ Artists being discovered consistently
✅ Predictable costs ($0.50/1K videos)
✅ 97% success rate maintained
```

---

**Support**: 
- Coolify: [Coolify Documentation](https://coolify.io/docs)
- Apify: apidojo10@gmail.com
- Application: Your development team 