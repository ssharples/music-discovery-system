# Music Discovery System - Agent Implementation Guide

## Quick Start: Applying Improvements to Existing Agents

This guide provides practical steps to upgrade your existing agents with the advanced PydanticAI and Crawl4AI features documented in `AGENT_IMPROVEMENTS_REPORT.md`.

## 1. Upgrading AI Data Cleaner (PydanticAI)

The `enhanced_ai_data_cleaner_example.py` demonstrates the full implementation. Here's how to upgrade your existing `ai_data_cleaner.py`:

### Step 1: Add Tool Support

```python
# In ai_data_cleaner.py, modify the agent initialization:

def _initialize_agents(self):
    # ... existing code ...
    
    # Artist name cleaning agent with tools
    self.agents['artist'] = Agent(
        model=model,
        result_type=CleanedArtistData,
        deps_type=CleanerContext,  # Add dependency type
        system_prompt="""...""",
        retries=3  # Add retry count
    )
    
    # Register tools after creation
    self._register_artist_tools()

def _register_artist_tools(self):
    """Add tools to the artist agent"""
    @self.agents['artist'].tool
    async def parse_follower_count(ctx: RunContext[CleanerContext], text: str) -> int:
        # Tool implementation
        pass
```

### Step 2: Implement Streaming

```python
# Add streaming method to AIDataCleaner class:

async def clean_artist_name_streaming(self, title: str, session_id: str):
    """Clean with real-time updates via WebSocket"""
    async with self.agents['artist'].run_stream(
        prompt=f"Clean: {title}",
        deps={"session_id": session_id}
    ) as result:
        async for partial, is_last in result.stream_structured(debounce_by=0.1):
            # Send partial results via WebSocket
            await notify_cleaning_progress(partial)
            if is_last:
                return partial
```

### Step 3: Add Custom Retry Logic

```python
# Add retry handler during initialization:

@self.agents['artist'].model_retry
async def handle_errors(ctx: RunContext, exception: Exception) -> ModelRetry:
    if "rate_limit" in str(exception).lower():
        await asyncio.sleep(5)
        return ModelRetry(content="Continue after rate limit")
    # Handle other error types
```

## 2. Upgrading Crawl4AI Agents

### Step 1: Add LLM Content Filtering

```python
# In crawl4ai_enrichment_agent.py:

from crawl4ai.content_filter import LLMContentFilter
from crawl4ai.llm_config import LLMConfig

async def _enrich_spotify(self, artist_profile: ArtistProfile, enriched_data: EnrichedArtistData):
    # Create LLM filter for Spotify content
    llm_config = LLMConfig(
        provider="deepseek",
        model="deepseek-chat",
        api_key=settings.DEEPSEEK_API_KEY
    )
    
    content_filter = LLMContentFilter(
        llm_config=llm_config,
        instruction="""Extract only: monthly listeners, bio, genres, social links.
                      Exclude: navigation, ads, recommendations.""",
        chunk_token_threshold=500
    )
    
    # Use in crawler config
    crawler_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(content_filter=content_filter),
        # ... other config
    )
```

### Step 2: Enhance JavaScript Interactions

```python
# In crawl4ai_youtube_agent.py, improve scrolling:

js_advanced_scroll = """
(async function() {
    // Strategy 1: Progressive scrolling
    for (let i = 0; i < 10; i++) {
        window.scrollBy(0, window.innerHeight);
        await new Promise(r => setTimeout(r, 1000));
    }
    
    // Strategy 2: Element-based scrolling
    const videos = document.querySelectorAll('ytd-video-renderer');
    for (let video of videos) {
        video.scrollIntoView({behavior: 'smooth'});
        await new Promise(r => setTimeout(r, 500));
    }
    
    // Strategy 3: Trigger lazy loading
    document.querySelectorAll('[data-lazy]').forEach(el => {
        el.dispatchEvent(new Event('focus'));
    });
})();
"""

crawler_config = CrawlerRunConfig(
    js_code=js_advanced_scroll,
    scan_full_page=True,
    magic=True  # Enable anti-bot features
)
```

### Step 3: Implement Session Management

```python
# Add session support for multi-step flows:

async def instagram_with_session(self, username: str):
    session_id = f"ig_{username}"
    
    # Step 1: Check if login needed
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=f"https://instagram.com/{username}",
            config=CrawlerRunConfig(
                session_id=session_id,
                js_code="window.__needs_login = !!document.querySelector('[href*=login]')"
            )
        )
    
    # Step 2: Continue with same session
    if result.js_result.get("__needs_login"):
        # Handle login flow
        pass
```

## 3. Integration with Orchestrator

Update the orchestrator to use enhanced agents:

```python
# In orchestrator.py:

class DiscoveryOrchestrator:
    def __init__(self):
        # Use enhanced agents
        self.ai_cleaner = EnhancedAIDataCleaner()  # New enhanced version
        self.enrichment_agent = EnhancedCrawl4AIEnrichmentAgent()
        
        # Configure streaming support
        self.enable_streaming = True
        
    async def _run_discovery_pipeline(self, session_id: UUID, request: DiscoveryRequest, deps: PipelineDependencies):
        # Use streaming for real-time updates
        if self.enable_streaming:
            cleaned = await self.ai_cleaner.clean_artist_name_streaming(
                title=video_title,
                session_id=str(session_id)
            )
        # Continue with enrichment...
```

## 4. Testing the Improvements

### Unit Tests

```python
# test_enhanced_agents.py

async def test_ai_cleaner_tools():
    """Test that AI cleaner uses tools correctly"""
    cleaner = EnhancedAIDataCleaner()
    result = await cleaner.clean_artist_name(
        "Drake ft. Future - Life Is Good (Official Music Video)"
    )
    
    assert result.artist_name == "Drake"
    assert "Future" in result.featured_artists
    assert len(result.tool_usage) > 0  # Verify tools were used
    assert result.confidence_score > 0.8

async def test_crawl4ai_llm_filter():
    """Test LLM content filtering"""
    agent = EnhancedCrawl4AIEnrichmentAgent()
    result = await agent.enrich_spotify_with_filter(test_artist)
    
    # Verify filtered content
    assert "cookie" not in result.extracted_content.lower()
    assert "monthly_listeners" in result.extracted_content
```

### Integration Tests

```python
async def test_full_discovery_flow():
    """Test complete discovery with all enhancements"""
    orchestrator = DiscoveryOrchestrator()
    
    # Monitor WebSocket messages
    messages = []
    async def capture_ws(msg):
        messages.append(msg)
    
    # Run discovery
    session_id = await orchestrator.start_discovery_session(
        request=DiscoveryRequest(search_query="indie music 2024"),
        deps=deps,
        background_tasks=BackgroundTasks()
    )
    
    # Verify streaming updates received
    assert any("partial_result" in msg for msg in messages)
    assert any("confidence" in msg for msg in messages)
```

## 5. Deployment Checklist

Before deploying the enhanced agents:

1. **Environment Variables**
   - Ensure `DEEPSEEK_API_KEY` is set
   - Configure rate limits appropriately

2. **Dependencies**
   ```bash
   pip install pydantic-ai>=0.2.0
   pip install crawl4ai>=0.4.0
   ```

3. **Database Updates**
   - Add columns for confidence scores
   - Add indexes for tool usage tracking

4. **Monitoring**
   - Set up alerts for low confidence scores
   - Monitor API usage and costs
   - Track tool execution times

5. **Gradual Rollout**
   - Test with 10% of traffic first
   - Monitor error rates and performance
   - Roll back if issues detected

## 6. Performance Optimization

### Caching Strategy

```python
# Add caching for repeated operations
from functools import lru_cache

@lru_cache(maxsize=1000)
async def cached_artist_validation(artist_name: str):
    """Cache artist name validation results"""
    return await validator.validate_artist_name(artist_name)
```

### Parallel Processing

```python
# Process multiple artists in parallel
async def enrich_artists_batch(artists: List[ArtistProfile]):
    tasks = [
        enrichment_agent.enrich_artist(artist)
        for artist in artists
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## 7. Troubleshooting

Common issues and solutions:

1. **Rate Limits**: Implement exponential backoff
2. **Memory Usage**: Use streaming for large datasets
3. **Timeout Errors**: Adjust `page_timeout` in CrawlerRunConfig
4. **Low Confidence Scores**: Review and update validation rules

## Next Steps

1. Start with AI Data Cleaner improvements (highest impact)
2. Add LLM filtering to Crawl4AI agents
3. Implement streaming for real-time updates
4. Deploy monitoring and alerts
5. Gather metrics and iterate

Remember to push each change to git and redeploy via Coolify/Docker Compose as per your workflow. 