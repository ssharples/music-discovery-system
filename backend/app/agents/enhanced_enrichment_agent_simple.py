"""
Simplified Enhanced Enrichment Agent that works reliably with PydanticAI.
"""
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile

# Import Firecrawl if available
try:
    import firecrawl
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancementData(BaseModel):
    """Structured enrichment data"""
    artist_name: str
    genre: Optional[str] = None
    contact_email: Optional[str] = None
    social_media_followers: Optional[int] = None
    website_info: Optional[str] = None
    enrichment_score: float = 0.0
    data_sources: List[str] = Field(default_factory=list)

class SimpleEnhancedEnrichmentAgent:
    """Simplified enrichment agent that works reliably"""
    
    def __init__(self):
        self.agent_name = "SimpleEnhancedEnrichmentAgent"
        self._agent: Optional[Agent] = None
        self._initialized = False
        logger.info(f"🤖 Initializing {self.agent_name}")
    
    @property
    def agent(self) -> Optional[Agent]:
        """Lazy initialization of PydanticAI agent"""
        if not self._initialized:
            self._initialize_agent()
        return self._agent
    
    def _initialize_agent(self):
        """Initialize agent with error handling"""
        try:
            # Use same pattern as existing working agents
            if settings.is_deepseek_configured():
                self._agent = Agent(
                    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
                    system_prompt="""You are an AI music industry researcher specializing in artist data enrichment.
                    
                    Your task is to analyze artist information and provide:
                    1. Genre classification based on available data
                    2. Contact information discovery patterns
                    3. Social media presence assessment
                    4. Overall data quality scoring
                    
                    Focus on emerging artists and provide practical, actionable insights.
                    Always return structured data that can be used for music industry decisions."""
                )
                self._initialized = True
                logger.info(f"✅ {self.agent_name} initialized with DeepSeek")
            else:
                logger.warning(f"⚠️ {self.agent_name} not initialized - no AI provider configured")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize {self.agent_name}: {e}")
            self._agent = None
    
    async def enrich_artist_basic(
        self,
        artist_profile: ArtistProfile,
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Basic artist enrichment using available data"""
        
        logger.info(f"🔍 Enriching artist: {artist_profile.name}")
        
        try:
            # Gather available data
            basic_info = {
                "name": artist_profile.name,
                "youtube_channel": artist_profile.metadata.get("youtube_channel_url", ""),
                "social_links": getattr(artist_profile, 'social_links', []),
                "subscriber_count": artist_profile.metadata.get("subscriber_count", 0),
                "video_count": artist_profile.metadata.get("video_count", 0)
            }
            
            # Enhanced data gathering with Firecrawl
            firecrawl_data = await self._gather_firecrawl_data(artist_profile, deps)
            if firecrawl_data:
                basic_info.update(firecrawl_data)
                logger.info(f"🔥 Enhanced data with Firecrawl for {artist_profile.name}")
            
            # Use AI agent if available
            if self.agent:
                analysis_prompt = f"""
                Analyze this artist data and provide enrichment insights:
                
                Artist: {artist_profile.name}
                YouTube Subscribers: {basic_info.get('subscriber_count', 0)}
                Video Count: {basic_info.get('video_count', 0)}
                Social Links: {basic_info.get('social_links', [])}
                
                Please provide:
                1. Likely genre based on the data
                2. Artist career stage (emerging/established)
                3. Contact discovery suggestions
                4. Data quality score (0-100)
                5. Key recommendations for music industry professionals
                
                Return as JSON with keys: genre, career_stage, contact_suggestions, quality_score, recommendations
                """
                
                try:
                    result = await self.agent.run(analysis_prompt, deps=deps)
                    
                    if result and hasattr(result, 'data'):
                        ai_insights = result.data
                        logger.info(f"✅ AI enrichment completed for {artist_profile.name}")
                        
                        return {
                            "success": True,
                            "artist_name": artist_profile.name,
                            "basic_info": basic_info,
                            "ai_insights": ai_insights,
                            "enrichment_score": 0.75,  # Default good score (0-1 scale)
                            "data_sources": ["youtube", "ai_analysis"],
                            "processed_at": datetime.now().isoformat()
                        }
                        
                except Exception as e:
                    logger.error(f"❌ AI enrichment failed: {e}")
                    # Fallback to basic enrichment
            
            # Basic enrichment without AI
            basic_score = self._calculate_basic_score(basic_info)
            
            return {
                "success": True,
                "artist_name": artist_profile.name,
                "basic_info": basic_info,
                "enrichment_score": basic_score,
                "data_sources": ["youtube"],
                "processed_at": datetime.now().isoformat(),
                "fallback_mode": True
            }
            
        except Exception as e:
            logger.error(f"❌ Enrichment failed for {artist_profile.name}: {e}")
            return {
                "success": False,
                "artist_name": artist_profile.name,
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
    
    def _calculate_basic_score(self, basic_info: Dict[str, Any]) -> float:
        """Calculate basic enrichment score without AI"""
        score = 0.0
        
        # Base score for having basic info
        if basic_info.get("name"):
            score += 20
        
        # YouTube presence
        subscriber_count = basic_info.get("subscriber_count", 0)
        if subscriber_count > 0:
            score += 30
            if subscriber_count > 1000:
                score += 10
            if subscriber_count > 10000:
                score += 10
        
        # Video content
        video_count = basic_info.get("video_count", 0)
        if video_count > 0:
            score += 20
            if video_count > 10:
                score += 10
        
        # Social media presence
        social_links = basic_info.get("social_links", [])
        if social_links:
            score += 10
        
        return min(score / 100.0, 1.0)  # Convert to 0-1 scale
    
    async def _gather_firecrawl_data(
        self, 
        artist_profile: ArtistProfile, 
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Gather additional data using Firecrawl for web scraping"""
        
        if not FIRECRAWL_AVAILABLE or not settings.is_firecrawl_configured():
            logger.debug("Firecrawl not available or configured")
            return {}
        
        try:
            from firecrawl import FirecrawlApp
            
            # Initialize Firecrawl client
            app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
            
            enrichment_data = {
                "firecrawl_sources": [],
                "web_mentions": 0,
                "social_presence": {},
                "contact_info": {}
            }
            
            # Try to find artist website or social media
            search_urls = []
            
            # Look for website in metadata
            if artist_profile.metadata.get("website"):
                search_urls.append(artist_profile.metadata["website"])
            
            # Generate potential social media URLs
            artist_name_clean = artist_profile.name.lower().replace(" ", "")
            potential_urls = [
                f"https://www.instagram.com/{artist_name_clean}/",
                f"https://twitter.com/{artist_name_clean}",
                f"https://www.facebook.com/{artist_name_clean}",
            ]
            
            # Crawl available URLs
            for url in search_urls + potential_urls[:2]:  # Limit to avoid quota issues
                try:
                    logger.info(f"🔥 Firecrawl scraping: {url}")
                    
                    scrape_result = app.scrape_url(
                        url,
                        params={
                            'formats': ['markdown', 'html'],
                            'timeout': 10000,
                            'waitFor': 2000
                        }
                    )
                    
                    if scrape_result and scrape_result.get('success'):
                        content = scrape_result.get('markdown', '')
                        
                        # Extract useful information
                        if content:
                            enrichment_data["firecrawl_sources"].append(url)
                            
                            # Look for contact information
                            contact_info = self._extract_contact_info(content)
                            if contact_info:
                                enrichment_data["contact_info"].update(contact_info)
                            
                            # Count social media mentions
                            social_mentions = content.lower().count("instagram") + \
                                            content.lower().count("twitter") + \
                                            content.lower().count("facebook")
                            
                            enrichment_data["web_mentions"] += len(content.split())
                            enrichment_data["social_presence"][url] = {
                                "content_length": len(content),
                                "social_mentions": social_mentions
                            }
                            
                            logger.info(f"✅ Firecrawl successfully scraped {url}")
                        
                except Exception as e:
                    logger.warning(f"Firecrawl failed for {url}: {e}")
                    continue
            
            # Return enrichment data if we found anything useful
            if enrichment_data["firecrawl_sources"]:
                logger.info(f"🔥 Firecrawl enriched {artist_profile.name} with {len(enrichment_data['firecrawl_sources'])} sources")
                return enrichment_data
            
        except Exception as e:
            logger.error(f"❌ Firecrawl enrichment failed: {e}")
        
        return {}
    
    def _extract_contact_info(self, content: str) -> Dict[str, str]:
        """Extract contact information from scraped content"""
        import re
        
        contact_info = {}
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        if emails:
            contact_info["email"] = emails[0]  # Take first email found
        
        # Phone patterns (basic)
        phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
        phones = re.findall(phone_pattern, content)
        if phones:
            contact_info["phone"] = phones[0]
        
        # Social media handles
        if "@" in content:
            # Look for social handles
            social_pattern = r'@([A-Za-z0-9_]{1,15})'
            handles = re.findall(social_pattern, content)
            if handles:
                contact_info["social_handle"] = f"@{handles[0]}"
        
        return contact_info

# Factory function for easy import
def get_simple_enhanced_enrichment_agent() -> SimpleEnhancedEnrichmentAgent:
    """Get simple enhanced enrichment agent instance"""
    return SimpleEnhancedEnrichmentAgent() 