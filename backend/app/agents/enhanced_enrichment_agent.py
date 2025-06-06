"""
Enhanced Enrichment Agent with Firecrawl integration and structured tools.
"""
from pydantic_ai.tools import Tool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union
import logging
import asyncio
import json
from datetime import datetime
import re

from app.agents.enhanced_agent_base import EnhancedAgentBase, AgentContext, AgentResponse
from app.core.dependencies import PipelineDependencies
from app.core.config import settings
from app.models.artist import ArtistProfile

logger = logging.getLogger(__name__)

class SocialMediaData(BaseModel):
    """Structured social media data model"""
    platform: str
    handle: Optional[str] = None
    url: Optional[str] = None
    followers: Optional[int] = None
    engagement_rate: Optional[float] = None
    verified: bool = False
    description: Optional[str] = None
    last_post_date: Optional[datetime] = None

class ContactInfo(BaseModel):
    """Structured contact information model"""
    email: Optional[str] = None
    website: Optional[str] = None
    booking_email: Optional[str] = None
    manager_contact: Optional[str] = None
    social_links: List[str] = Field(default_factory=list)

class EnrichmentResult(BaseModel):
    """Structured enrichment result"""
    artist_name: str
    social_media: List[SocialMediaData] = Field(default_factory=list)
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    genre: Optional[str] = None
    career_stage: Optional[str] = None
    market_presence: Dict[str, Any] = Field(default_factory=dict)
    enrichment_score: float = 0.0
    sources: List[str] = Field(default_factory=list)
    confidence: float = 0.0

class FirecrawlScrapingTool(Tool):
    """Advanced Firecrawl scraping tool for artist data"""
    
    async def scrape_artist_website(self, url: str) -> Dict[str, Any]:
        """Scrape artist website with structured extraction"""
        try:
            import firecrawl
            
            if not settings.FIRECRAWL_API_KEY:
                return {"error": "Firecrawl not configured"}
            
            app = firecrawl.FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
            
            # Schema for extracting artist information
            extraction_schema = {
                "type": "object",
                "properties": {
                    "artist_name": {"type": "string"},
                    "genre": {"type": "string"},
                    "bio": {"type": "string"},
                    "contact_email": {"type": "string"},
                    "booking_email": {"type": "string"},
                    "social_media": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "platform": {"type": "string"},
                                "url": {"type": "string"}
                            }
                        }
                    },
                    "upcoming_events": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "discography": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
            
            result = app.scrape_url(
                url=url,
                params={
                    'formats': ['extract', 'markdown'],
                    'extract': {
                        'schema': extraction_schema
                    }
                }
            )
            
            return {
                "success": True,
                "data": result.get('extract', {}),
                "content": result.get('markdown', ''),
                "source": url
            }
            
        except Exception as e:
            logger.error(f"❌ Website scraping failed for {url}: {e}")
            return {"success": False, "error": str(e)}
    
    async def scrape_social_platform(self, url: str, platform: str) -> Dict[str, Any]:
        """Scrape social media platform with platform-specific extraction"""
        try:
            import firecrawl
            
            if not settings.FIRECRAWL_API_KEY:
                return {"error": "Firecrawl not configured"}
            
            app = firecrawl.FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
            
            # Platform-specific schemas
            schemas = {
                "instagram": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "followers": {"type": "number"},
                        "following": {"type": "number"},
                        "posts_count": {"type": "number"},
                        "bio": {"type": "string"},
                        "verified": {"type": "boolean"},
                        "recent_posts": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "twitter": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "followers": {"type": "number"},
                        "following": {"type": "number"},
                        "tweets_count": {"type": "number"},
                        "bio": {"type": "string"},
                        "verified": {"type": "boolean"},
                        "location": {"type": "string"}
                    }
                }
            }
            
            schema = schemas.get(platform, schemas["instagram"])
            
            result = app.scrape_url(
                url=url,
                params={
                    'formats': ['extract'],
                    'extract': {
                        'schema': schema
                    }
                }
            )
            
            return {
                "success": True,
                "platform": platform,
                "data": result.get('extract', {}),
                "source": url
            }
            
        except Exception as e:
            logger.error(f"❌ Social platform scraping failed for {url}: {e}")
            return {"success": False, "error": str(e)}

class SpotifyEnrichmentTool(Tool):
    """Spotify data enrichment tool"""
    
    async def get_artist_data(self, artist_name: str) -> Dict[str, Any]:
        """Get comprehensive Spotify artist data"""
        try:
            # This would integrate with Spotify API
            # For now, return structured placeholder
            return {
                "success": True,
                "data": {
                    "spotify_id": f"spotify_{artist_name.lower()}",
                    "followers": 0,
                    "genres": [],
                    "popularity": 0,
                    "monthly_listeners": 0,
                    "top_tracks": []
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class EmailDiscoveryTool(Tool):
    """AI-powered email discovery tool"""
    
    async def find_contact_emails(self, artist_name: str, website: Optional[str] = None) -> List[str]:
        """Discover contact emails using various methods"""
        emails = []
        
        # Pattern-based email discovery
        if website:
            common_patterns = [
                f"booking@{self._extract_domain(website)}",
                f"info@{self._extract_domain(website)}",
                f"contact@{self._extract_domain(website)}",
                f"{artist_name.lower().replace(' ', '.')}@{self._extract_domain(website)}"
            ]
            emails.extend(common_patterns)
        
        # Social media bio parsing (would be enhanced with actual scraping)
        # This is a placeholder for more sophisticated email discovery
        
        return list(set(emails))  # Remove duplicates
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        import re
        match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
        return match.group(1) if match else ""

class EnhancedEnrichmentAgent(EnhancedAgentBase):
    """Enhanced enrichment agent with Firecrawl and structured tools"""
    
    def __init__(self):
        super().__init__("EnhancedEnrichmentAgent")
        self.firecrawl_tool = FirecrawlScrapingTool()
        self.spotify_tool = SpotifyEnrichmentTool()
        self.email_tool = EmailDiscoveryTool()
    
    def get_system_prompt(self) -> str:
        return """You are an AI music industry researcher specializing in artist enrichment and data collection.
        
        Your expertise includes:
        1. **Social Media Analysis**: Extract follower counts, engagement rates, content quality
        2. **Contact Discovery**: Find booking emails, management contacts, official websites
        3. **Market Assessment**: Evaluate artist's commercial potential and industry presence
        4. **Data Validation**: Verify information accuracy and remove duplicates
        5. **Trend Analysis**: Identify growth patterns and career trajectory
        
        Key Focus Areas:
        - Emerging artists (10K-100K followers range)
        - Active social media presence (posts within 30 days)
        - Professional presentation and branding
        - Accessible contact information
        - Genre classification and market fit
        
        Always prioritize data accuracy and provide confidence scores for your findings.
        """
    
    def _get_tools(self) -> List[Tool]:
        return [
            self.firecrawl_tool,
            self.spotify_tool,
            self.email_tool
        ]
    
    async def enrich_artist_profile(
        self,
        artist_profile: ArtistProfile,
        context: AgentContext,
        deps: PipelineDependencies
    ) -> EnrichmentResult:
        """Comprehensive artist profile enrichment"""
        
        logger.info(f"🔍 Enriching profile for {artist_profile.name}")
        
        # Step 1: Website analysis
        website_data = None
        if artist_profile.website_url:
            website_data = await self.firecrawl_tool.scrape_artist_website(
                artist_profile.website_url
            )
        
        # Step 2: Social media enrichment
        social_media_data = []
        for social_link in artist_profile.social_links:
            platform = self._detect_platform(social_link)
            if platform:
                social_data = await self.firecrawl_tool.scrape_social_platform(
                    social_link, platform
                )
                if social_data.get("success"):
                    social_media_data.append(SocialMediaData(
                        platform=platform,
                        url=social_link,
                        **social_data.get("data", {})
                    ))
        
        # Step 3: Spotify data
        spotify_data = await self.spotify_tool.get_artist_data(artist_profile.name)
        
        # Step 4: Contact discovery
        contact_emails = await self.email_tool.find_contact_emails(
            artist_profile.name,
            artist_profile.website_url
        )
        
        # Step 5: AI analysis of collected data
        analysis_prompt = f"""
        Analyze this artist data and provide comprehensive enrichment:
        
        Artist: {artist_profile.name}
        Website Data: {json.dumps(website_data, indent=2) if website_data else 'None'}
        Social Media: {[sm.model_dump() for sm in social_media_data]}
        Spotify Data: {spotify_data}
        Contact Emails: {contact_emails}
        
        Provide:
        1. Genre classification
        2. Career stage assessment (emerging/established/veteran)
        3. Market presence evaluation
        4. Enrichment quality score (0-100)
        5. Confidence level in the data
        6. Key insights and recommendations
        """
        
        analysis_result = await self.run_with_context(
            analysis_prompt,
            context,
            deps
        )
        
        # Step 6: Compile enrichment result
        enrichment_result = EnrichmentResult(
            artist_name=artist_profile.name,
            social_media=social_media_data,
            contact_info=ContactInfo(
                email=contact_emails[0] if contact_emails else None,
                website=artist_profile.website_url,
                social_links=artist_profile.social_links
            ),
            sources=[
                artist_profile.website_url,
                *artist_profile.social_links,
                "spotify_api"
            ]
        )
        
        if analysis_result.success and analysis_result.data:
            ai_analysis = analysis_result.data
            enrichment_result.genre = ai_analysis.get("genre")
            enrichment_result.career_stage = ai_analysis.get("career_stage")
            enrichment_result.market_presence = ai_analysis.get("market_presence", {})
            enrichment_result.enrichment_score = ai_analysis.get("enrichment_score", 0.0)
            enrichment_result.confidence = ai_analysis.get("confidence", 0.0)
        
        logger.info(f"✅ Enrichment completed for {artist_profile.name} (Score: {enrichment_result.enrichment_score})")
        
        return enrichment_result
    
    def _detect_platform(self, url: str) -> Optional[str]:
        """Detect social media platform from URL"""
        platform_patterns = {
            "instagram": ["instagram.com", "instagr.am"],
            "twitter": ["twitter.com", "x.com"],
            "facebook": ["facebook.com", "fb.com"],
            "tiktok": ["tiktok.com"],
            "spotify": ["spotify.com"],
            "soundcloud": ["soundcloud.com"],
            "bandcamp": ["bandcamp.com"]
        }
        
        url_lower = url.lower()
        for platform, patterns in platform_patterns.items():
            if any(pattern in url_lower for pattern in patterns):
                return platform
        
        return None

# Factory function for backward compatibility
def get_enhanced_enrichment_agent() -> EnhancedEnrichmentAgent:
    """Get enhanced enrichment agent instance"""
    return EnhancedEnrichmentAgent() 