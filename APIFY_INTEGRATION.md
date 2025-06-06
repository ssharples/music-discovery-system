# 🏯 Apify YouTube Scraper Integration Guide

## Overview

This guide helps you integrate the [Apify YouTube Scraper](https://apify.com/apidojo/youtube-scraper) to replace the official YouTube Data API and bypass quota limitations.

## ✅ Benefits Over Official YouTube API

| Feature | Official YouTube API | Apify YouTube Scraper |
|---------|---------------------|----------------------|
| **Quota Limitations** | ❌ 10,000 units/day | ✅ No quotas |
| **Cost** | ❌ Expensive after quota | ✅ $0.50 per 1,000 videos |
| **Success Rate** | ❌ Quota failures | ✅ 97% success rate |
| **Speed** | ⚠️ Rate limited | ✅ 10+ videos/second |
| **Data Completeness** | ⚠️ Limited fields | ✅ Full video data |
| **Setup Complexity** | ❌ OAuth, API keys | ✅ Single API token |

## 🚀 Quick Setup

### Option A: Automated Setup (Recommended)

```bash
# 1. Run environment setup
python setup_apify_env.py

# 2. Run complete migration (creates backups)
python migrate_to_apify.py

# 3. Test integration
python test_apify_integration.py
```

### Option B: Manual Setup

1. **Get Apify API Token**
   - Sign up at [Apify.com](https://apify.com/)
   - Go to [Account Integrations](https://console.apify.com/account/integrations)
   - Copy your API token

2. **Configure Environment**
   ```bash
   # Add to your .env file
   APIFY_API_TOKEN=your_apify_token_here
   ```

3. **Test Integration**
   ```bash
   python test_apify_integration.py
   ```

Expected output:
```
🧪 Testing Apify YouTube Agent Integration
✅ APIFY_API_TOKEN configured
🎵 Test 1: Searching for music content...
✅ Successfully found 5 music videos
💰 Cost for this test: $0.0025
🎉 All tests completed successfully!
```

### 3. Update Your Orchestrator

Replace the YouTube agent in your orchestrator:

```python
# OLD - Official YouTube API
from app.agents.youtube_agent import YouTubeAgent
youtube_agent = YouTubeAgent()

# NEW - Apify YouTube Scraper  
from app.agents.apify_youtube_agent import ApifyYouTubeAgent
youtube_agent = ApifyYouTubeAgent()
```

## 📊 API Usage Examples

### Search for Music Content

```python
from app.agents.apify_youtube_agent import ApifyYouTubeAgent

agent = ApifyYouTubeAgent()

# Search for new indie music
results = agent.search_music_content(
    keywords=["indie rock 2024", "new music"],
    max_results=50,
    upload_date="month",  # hour, today, week, month, year
    duration="all",       # short, long, all
    sort_by="relevance"   # relevance, date, views, rating
)

print(f"Found {len(results)} videos")
for video in results[:3]:
    print(f"- {video['title']} by {video['extracted_artist_name']}")
```

### Get Videos from Specific Channels

```python
# Get videos from music channels
channel_urls = [
    "https://www.youtube.com/@Pitchfork",
    "https://www.youtube.com/@KEXP",
    "https://www.youtube.com/@NPRMusic"
]

videos = agent.get_channel_videos(
    channel_urls=channel_urls,
    max_videos_per_channel=20
)
```

### Get Trending Music

```python
# Get trending music videos
trending = agent.get_trending_music(max_results=30)

music_videos = [v for v in trending if 'music' in v['title'].lower()]
print(f"Found {len(music_videos)} trending music videos")
```

## 💰 Cost Management

### Calculate Costs

```python
# Estimate costs before running
estimated_videos = 1000
cost = agent.get_cost_estimate(estimated_videos)
print(f"Estimated cost: ${cost:.2f}")  # $0.50
```

### Monitor Usage

- Track usage at: [Apify Console Billing](https://console.apify.com/account/billing)
- Set up billing alerts to avoid surprises
- Current rate: **$0.50 per 1,000 videos**

### Cost Comparison

| Scenario | Official YouTube API | Apify Scraper |
|----------|---------------------|---------------|
| 1,000 videos/day | Quota exceeded ❌ | $0.50/day ✅ |
| 10,000 videos/day | $200-300/day ❌ | $5/day ✅ |
| 50,000 videos/day | $1000+/day ❌ | $25/day ✅ |

## 🔧 Technical Integration

### Update Orchestrator

In `backend/app/agents/orchestrator.py`:

```python
# Add at the top
from app.agents.apify_youtube_agent import ApifyYouTubeAgent

class Orchestrator:
    def __init__(self):
        # Replace YouTube agent
        self.youtube_agent = ApifyYouTubeAgent()
        # ... rest of your agents
    
    async def discover_artists(self):
        """Updated discovery method using Apify"""
        
        # Search for music content
        music_keywords = [
            "new music 2024",
            "indie artists",
            "emerging musicians",
            "underground music"
        ]
        
        videos = self.youtube_agent.search_music_content(
            keywords=music_keywords,
            max_results=100,
            upload_date="week"
        )
        
        # Process videos to extract artists
        discovered_artists = []
        for video in videos:
            if video.get('extracted_artist_name'):
                artist_data = {
                    'name': video['extracted_artist_name'],
                    'source_video_id': video['video_id'],
                    'source_channel': video['channel_title'],
                    'discovery_metadata': {
                        'views': video['view_count'],
                        'likes': video['like_count'],
                        'source': 'apify_youtube'
                    }
                }
                discovered_artists.append(artist_data)
        
        return discovered_artists
```

### Enhanced Artist Extraction

The Apify agent includes the same artist extraction logic you implemented:

```python
# These patterns are built into the agent
patterns = [
    r'^([^-]+)\s*-\s*',      # "Artist - Song"
    r'^([^|]+)\s*\|\s*',     # "Artist | Song" 
    r'\s*by\s+([^(\[]+)',    # "Song by Artist"
    r'^([^:]+):\s*',         # "Artist: Song"
]
```

## 📈 Data Schema

### Video Data Structure

Each video result includes:

```python
{
    'video_id': 'dQw4w9WgXcQ',
    'title': 'Rick Astley - Never Gonna Give You Up',
    'description': 'Official music video...',
    'channel_id': 'UCuAXFkgsw1L7xaCfnd5JJOw',
    'channel_title': 'Rick Astley',
    'channel_url': 'http://www.youtube.com/@RickAstley',
    'extracted_artist_name': 'Rick Astley',
    'published_at': 'Oct 25, 2009',
    'duration_seconds': 212,
    'view_count': 1500000000,
    'like_count': 15000000,
    'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'thumbnail_url': 'https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg',
    'is_live': false,
    'data_source': 'apify_youtube'
}
```

### Integration with Enrichment

The Apify data works seamlessly with your existing enrichment system:

```python
# In your enrichment agent
def enrich_artist_data(self, artist_data):
    """Enrich artist discovered via Apify"""
    
    artist_name = artist_data.get('extracted_artist_name')
    if not artist_name:
        return artist_data
    
    # Use Spotify API
    spotify_data = self.spotify_client.search_artist(artist_name)
    
    # Use Firecrawl for additional data
    firecrawl_data = self.firecrawl_client.scrape_artist_info(artist_name)
    
    # Combine all data sources
    enriched_data = {
        **artist_data,
        'spotify_data': spotify_data,
        'firecrawl_data': firecrawl_data,
        'enrichment_timestamp': datetime.utcnow()
    }
    
    return enriched_data
```

## ⚠️ Important Considerations

### Terms of Service

According to the Apify scraper terms:
- Minimum 10 items per keyword/URL
- Maximum 5 keywords/URLs per run
- Maximum 1-2 concurrent runs
- Wait a few minutes between runs

### Best Practices

1. **Batch Requests**: Group related searches together
2. **Rate Limiting**: Don't exceed 2 concurrent runs
3. **Cost Monitoring**: Set up billing alerts
4. **Error Handling**: Implement retry logic for failures
5. **Data Validation**: Verify artist extraction quality

### Error Handling

```python
try:
    results = agent.search_music_content(keywords=["indie rock"])
    if not results:
        logger.warning("No results from Apify - trying alternative keywords")
        results = agent.search_music_content(keywords=["alternative music"])
except Exception as e:
    logger.error(f"Apify search failed: {e}")
    # Fallback to cached data or alternative source
```

## 🎯 Expected Results

After integration, you should see:

1. **No More Quota Issues**: Unlimited YouTube data access
2. **Better Cost Control**: Predictable $0.50/1000 videos pricing
3. **Higher Success Rate**: 97% vs quota failures
4. **Faster Processing**: 10+ videos/second
5. **Same Data Quality**: All video metadata + artist extraction

## 🔍 Monitoring & Debugging

### Logs to Watch

```
INFO:ApifyYouTubeAgent:Starting Apify YouTube search with keywords: ['indie rock 2024']
INFO:ApifyYouTubeAgent:Successfully scraped 50 videos from YouTube
INFO:ApifyYouTubeAgent:Found 25 music-related trending videos
```

### Common Issues

| Issue | Cause | Solution |
|-------|--------|----------|
| No results | Invalid API token | Check `APIFY_API_TOKEN` in .env |
| Timeout errors | Long-running search | Reduce `max_results` |
| High costs | Large searches | Use `get_cost_estimate()` first |
| Missing artists | Bad extraction | Review title patterns |

## 📞 Support

- **Apify Support**: apidojo10@gmail.com
- **Actor Documentation**: [apify.com/apidojo/youtube-scraper](https://apify.com/apidojo/youtube-scraper)
- **Apify Console**: [console.apify.com](https://console.apify.com/)

---

🎉 **You're all set!** The Apify YouTube Scraper will solve your quota issues and provide reliable, cost-effective YouTube data access for your music discovery system. 