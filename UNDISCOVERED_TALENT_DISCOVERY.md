# Undiscovered Talent Discovery System

## Overview

The Undiscovered Talent Discovery system is a specialized feature designed to find emerging and independent artists who have recently uploaded high-quality music videos but haven't yet gained widespread recognition.

## Key Features

### 🎯 **Discovery Criteria**
- **Recent Uploads**: Videos uploaded within the last 24 hours
- **Low View Count**: Less than 50,000 views per video
- **Quality Content**: Must contain "official" in the title
- **Independent Artists**: Filters out major label content

### 🔍 **Search Strategy**
The system uses multiple targeted search terms:
- "official music video"
- "new music video" 
- "debut music video"
- "independent artist music video"
- "unsigned artist music video"

### 📊 **Scoring Algorithm**
Each discovered video receives an "undiscovered score" based on:

#### Base Score Components:
- **View Count Tiers**:
  - < 1,000 views: +0.4 points
  - 1,000-5,000 views: +0.3 points
  - 5,000-15,000 views: +0.2 points
  - 15,000-30,000 views: +0.1 points

- **Independent Indicators**: +0.3 points
  - Keywords: "independent", "indie", "unsigned", "debut", "emerging"

- **Quality Indicators**: +0.2 points
  - Must contain: "official music video", "official video", "music video"

- **Recency Bonus**: +0.1 points
  - Very recent uploads (hours/minutes ago)

- **Small Channel Bonus**: +0.1 points
  - Estimated from low view counts (< 2,000 views)

#### Penalty System:
- **Spam/Clickbait**: -0.2 points
  - Keywords: "click", "viral", "trending", "reaction", "cover", "remix"

### 🚫 **Filtering System**

#### Major Label Exclusion:
Automatically filters out content from established labels:
- VEVO channels
- Major labels: Universal, Sony, Warner, Atlantic, Capitol, RCA, etc.
- Music groups and entertainment companies

#### Quality Requirements:
- Minimum undiscovered score: 0.3
- Must contain "official" in title
- View count under 50,000
- Uploaded within 24 hours

## API Usage

### Endpoint
```
POST /api/discover/undiscovered-talent
```

### Parameters
- `max_results` (optional): Maximum number of artists to return (default: 50)

### Example Request
```bash
curl -X POST "http://localhost:8000/api/discover/undiscovered-talent?max_results=25" \
  -H "Content-Type: application/json"
```

### Example Response
```json
{
  "status": "success",
  "message": "Successfully discovered 15 undiscovered artists",
  "data": {
    "query": "undiscovered talent discovery",
    "total_found": 15,
    "artists": [...],
    "execution_time": 45.3,
    "discovery_criteria": "24h uploads, <50k views, independent artists",
    "pipeline_stats": {
      "videos_analyzed": 120,
      "channels_found": 35,
      "enriched_artists": 15,
      "estimated_cost": "$0.0240"
    }
  }
}
```

## Configuration

### Environment Variables
All existing Apify configuration applies:
- `APIFY_API_TOKEN`: Required for YouTube scraping
- `APIFY_ACTOR_TIMEOUT`: Timeout for actor runs (default: 600s)
- `APIFY_HTTP_TIMEOUT`: HTTP request timeout (default: 180s)
- `APIFY_MAX_RETRIES`: Maximum retry attempts (default: 3)

### Search Parameters
The system automatically configures optimal parameters:
- `uploadDate`: "today" (last 24 hours)
- `sort`: "date" (newest first)
- `maxItems`: 2x max_results (for filtering)
- `features`: "all"
- `gl`: "us", `hl`: "en"

## Integration with Existing System

### Orchestrator Integration
- Uses existing `DiscoveryOrchestrator` class
- Leverages all timeout fixes and fallback mechanisms
- Integrates with AI detection and enrichment pipeline
- Maintains all error handling and retry logic

### Artist Processing
1. **Video Discovery**: Specialized undiscovered talent search
2. **Channel Grouping**: Groups videos by artist/channel
3. **Quality Filtering**: Applies undiscovered artist criteria
4. **AI Detection**: Filters out AI-generated content
5. **Enrichment**: Full artist profile enrichment
6. **Storage**: Stores in existing database tables

### Quality Threshold
- Lower enrichment score threshold (0.2 vs 0.3) for undiscovered artists
- Emphasizes potential over current metrics
- Prioritizes emerging talent identification

## Technical Implementation

### Core Methods

#### `discover_undiscovered_artists()` 
Main discovery method in `ApifyYouTubeAgent`
- Generates targeted search URLs
- Configures optimal search parameters
- Processes and filters results

#### `_filter_for_undiscovered_artists()`
Advanced filtering logic
- Applies view count thresholds
- Checks for quality indicators
- Excludes major label content
- Calculates undiscovered scores

#### `_calculate_undiscovered_score()`
Sophisticated scoring algorithm
- Multi-factor analysis
- Weighted scoring system
- Spam detection and penalties

### Performance Optimizations
- **Batch Processing**: Processes videos in optimal chunks
- **Parallel Grouping**: Efficiently groups videos by channel
- **Smart Filtering**: Early elimination of unsuitable content
- **Rate Limiting**: Respectful API usage with delays

## Use Cases

### 🎵 **Music Industry Professionals**
- A&R scouts looking for fresh talent
- Playlist curators seeking new content
- Music bloggers and journalists
- Independent label executives

### 🎬 **Content Discovery**
- Emerging artist showcases
- New music highlights
- Independent artist features
- Daily discovery content

### 📊 **Market Analysis**
- Trend identification in emerging music
- Independent artist landscape analysis
- Genre emergence tracking
- Regional talent discovery

## Best Practices

### 🕒 **Timing**
- Run discovery during peak upload times
- Consider timezone differences for global coverage
- Regular scheduled runs for consistent coverage

### 🎯 **Result Analysis**
- Review undiscovered scores for quality
- Check artist backgrounds for authenticity
- Verify independence status
- Assess commercial potential

### 📈 **Follow-up Actions**
- Monitor discovered artists over time
- Track view count growth
- Identify breakthrough moments
- Build artist databases for future reference

## Monitoring and Analytics

### Success Metrics
- Number of undiscovered artists found
- Quality scores of discoveries
- Conversion rate (videos → viable artists)
- Cost per discovery

### Performance Tracking
- API response times
- Search success rates
- Filter effectiveness
- Enrichment completion rates

## Troubleshooting

### Common Issues
1. **No Results Found**
   - Check upload timing (24h window)
   - Verify search parameters
   - Review filter criteria

2. **Low Quality Results**
   - Adjust undiscovered score threshold
   - Review major label filter list
   - Check spam detection keywords

3. **API Timeouts**
   - All existing timeout fixes apply
   - Automatic fallback to smaller searches
   - Retry mechanisms activated

### Debug Information
- Detailed logging for each discovery step
- Score breakdown for filtering decisions
- Performance metrics for optimization
- Error tracking for improvements 