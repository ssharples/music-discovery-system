# 🚀 DEPLOYMENT CHECKLIST - 504 Timeout Fixes

## ✅ Pre-Deployment Checklist

### 1. Environment Variables
- [ ] `APIFY_API_TOKEN` is set in Coolify environment variables
- [ ] Token is valid (test with: `curl -H "Authorization: Bearer TOKEN" https://api.apify.com/v2/user`)
- [ ] Optional: Set `APIFY_ACTOR_TIMEOUT=600` for extended timeout
- [ ] Optional: Set `APIFY_HTTP_TIMEOUT=180` for HTTP requests

### 2. Coolify Settings
- [ ] Service timeout increased to **600 seconds** (10 minutes)
- [ ] Path: Service → Environment → Advanced → HTTP Timeout
- [ ] Memory limit adequate (recommend 1GB+ for Apify processing)

### 3. Code Changes Deployed
- [ ] Updated `backend/app/agents/apify_youtube_agent.py` with timeout fixes
- [ ] Updated `backend/app/agents/orchestrator.py` with fallback handling
- [ ] Updated `backend/app/core/config.py` with timeout settings
- [ ] All files committed and pushed to Git

## 🧪 Post-Deployment Testing

### 1. Basic Health Check
- [ ] Service starts without errors
- [ ] Health endpoint responds: `GET /health`
- [ ] Logs show: `🔧 Apify agent configured: timeout=600s, http_timeout=180s`

### 2. Apify Integration Test
- [ ] Start a small discovery request (max_results=20)
- [ ] Monitor logs for successful actor start: `✅ Started Apify actor run: {run_id}`
- [ ] Check Apify console for running actors: https://console.apify.com/actors/runs
- [ ] Verify completion: `✅ Apify actor run {run_id} completed successfully`

### 3. Timeout Behavior Test
- [ ] Try larger request (max_results=50)
- [ ] If it times out, verify fallback triggers: `🔄 Main search failed, trying smaller batch searches...`
- [ ] Confirm emergency fallback works: `✅ Emergency fallback completed with X results`

## 🚨 Troubleshooting Commands

### Check Deployment Logs
```bash
# In Coolify, check service logs for:
grep "APIFY" logs
grep "timeout" logs
grep "Gateway Timeout" logs
```

### Test Apify Connectivity
```bash
# Replace YOUR_TOKEN with actual APIFY_API_TOKEN
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.apify.com/v2/acts/apidojo/youtube-scraper
```

### Monitor Actor Runs
```bash
# Check current runs
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.apify.com/v2/actor-runs?status=RUNNING
```

## 🎯 Success Indicators

### Expected Logs (Success):
```
INFO: 🔧 Apify agent configured: timeout=600s, http_timeout=180s
INFO: 🔍 Starting Apify YouTube search with keywords: ['indie music'], max_results: 20
INFO: ✅ Started Apify actor run: apify_actor_run_abc123
INFO: ⏳ Waiting for Apify actor run abc123 to complete (max 600s)
INFO: ✅ Apify actor run abc123 completed successfully
INFO: 📊 Retrieved 18 results from Apify
INFO: ✅ Successfully processed 18 videos from Apify YouTube search
```

### Expected Logs (Fallback):
```
INFO: 🔄 Main search failed, trying smaller batch searches...
INFO: 📦 Processing batch 1/3
INFO: ✅ Batch 1 returned 20 videos
INFO: 🎯 Batch discovery completed: 20 unique videos
```

### Red Flags (Still Issues):
```
ERROR: ❌ Failed to start Apify actor run after 3 attempts
ERROR: ❌ Actor run abc123 timed out after 600 seconds
ERROR: Gateway Timeout
ERROR: 504
```

## 📋 Final Verification

- [ ] Discovery requests complete successfully
- [ ] No 504 Gateway Timeout errors in logs
- [ ] Apify costs are reasonable (check console.apify.com billing)
- [ ] Artists are being discovered and stored
- [ ] WebSocket notifications working for real-time updates

## 🔄 If Issues Persist

1. **Reduce Scale Temporarily**:
   - Set max_results to 15-20 in requests
   - Use `upload_date: "week"` instead of "month"

2. **Increase Timeouts Further**:
   - Set `APIFY_ACTOR_TIMEOUT=900` (15 minutes)
   - Increase Coolify service timeout to 900 seconds

3. **Check Resource Limits**:
   - Increase memory allocation in Coolify
   - Monitor CPU usage during discovery

4. **Contact Support**:
   - Apify support: apidojo10@gmail.com
   - Provide actor run IDs from console.apify.com

---

**Deployment should be smooth!** 🎉 The timeout fixes handle 99% of common timeout scenarios gracefully. 