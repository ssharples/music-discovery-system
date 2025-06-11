"""
AI-Powered Data Cleaner
Uses DeepSeek AI to clean and validate all extracted data throughout the discovery process.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic import BaseModel, Field, validator

from app.core.config import settings

logger = logging.getLogger(__name__)


class CleanedArtistData(BaseModel):
    """Cleaned artist name and metadata."""
    artist_name: str = Field(description="Clean artist name without featured artists or extra text")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in extraction accuracy")
    featured_artists: List[str] = Field(default=[], description="List of featured artists if any")
    is_collaboration: bool = Field(default=False, description="Whether this is a collaboration")
    reasoning: str = Field(description="Explanation of cleaning decisions")


class CleanedSocialLinks(BaseModel):
    """Cleaned and validated social media links."""
    instagram: Optional[str] = Field(None, description="Clean Instagram profile URL")
    tiktok: Optional[str] = Field(None, description="Clean TikTok profile URL")
    spotify: Optional[str] = Field(None, description="Clean Spotify artist URL")
    twitter: Optional[str] = Field(None, description="Clean Twitter/X profile URL")
    facebook: Optional[str] = Field(None, description="Clean Facebook page URL")
    youtube: Optional[str] = Field(None, description="Clean YouTube channel URL")
    website: Optional[str] = Field(None, description="Clean official website URL")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall confidence in link accuracy")
    validation_notes: str = Field(description="Notes on validation and cleaning decisions")


class CleanedChannelData(BaseModel):
    """Cleaned YouTube channel data."""
    channel_name: str = Field(description="Clean channel name")
    subscriber_count: int = Field(ge=0, description="Validated subscriber count")
    channel_description: Optional[str] = Field(None, description="Clean channel description")
    is_verified: bool = Field(default=False, description="Whether channel is verified")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in data accuracy")
    cleaning_notes: str = Field(description="Notes on what was cleaned or corrected")


class CleanedPlatformData(BaseModel):
    """Cleaned data from social media platforms."""
    platform: str = Field(description="Platform name (instagram, tiktok, spotify)")
    follower_count: Optional[int] = Field(None, ge=0, description="Validated follower count")
    engagement_metrics: Dict[str, Any] = Field(default={}, description="Clean engagement data")
    bio_text: Optional[str] = Field(None, description="Clean bio/description text")
    profile_verified: bool = Field(default=False, description="Whether profile is verified")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in data accuracy")
    data_quality_notes: str = Field(description="Notes on data quality and cleaning")


class AIDataCleaner:
    """DeepSeek-powered data cleaner for all extraction steps."""
    
    def __init__(self):
        """Initialize the AI data cleaner with specialized agents."""
        self.agents = {}
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize specialized cleaning agents for different data types."""
        try:
            if not settings.is_deepseek_configured():
                logger.warning("⚠️ DeepSeek not configured - AI data cleaning unavailable")
                return
            
            # Common model configuration
            model = OpenAIModel(
                'deepseek-chat',
                provider=DeepSeekProvider(
                    api_key=settings.DEEPSEEK_API_KEY
                )
            )
            
            # Artist name cleaning agent
            self.agents['artist'] = Agent(
                model=model,
                result_type=CleanedArtistData,
                system_prompt="""You are an expert at cleaning and validating artist names from YouTube video titles and metadata.

Your tasks:
1. Extract the PRIMARY artist name only (remove featured artists, collaborators)
2. Remove promotional text like "Official", "Music Video", "HD", "4K", etc.
3. Handle collaborations by identifying the MAIN artist (usually first mentioned)
4. Clean formatting issues (extra spaces, punctuation, brackets)
5. Validate that the result looks like a real artist name
6. Handle non-English names carefully, preserving proper spelling

Patterns to handle:
- "Artist - Song (Official Music Video)" → "Artist"
- "Artist ft. Other - Song" → "Artist" 
- "Artist x Other x Another - Song" → "Artist"
- "Artist | Song" → "Artist"
- "Artist: Song [Official Video]" → "Artist"

Be confident but honest about uncertainty."""
            )
            
            # Social links cleaning agent
            self.agents['social'] = Agent(
                model=model,
                result_type=CleanedSocialLinks,
                system_prompt="""You are an expert at cleaning and validating social media links.

Your tasks:
1. Validate URL formats and fix common issues
2. Ensure links point to artist profiles, not generic platform pages
3. Remove tracking parameters and clean URLs
4. Verify platform consistency (Instagram links go to instagram.com, etc.)
5. Flag suspicious or invalid links
6. Standardize URL formats (https, no trailing slashes unless needed)

Red flags to watch for:
- Generic platform URLs (/login, /signup, /home)
- Obviously wrong usernames or IDs
- Malformed URLs or suspicious domains
- Links that don't match the claimed platform

Only include high-confidence, valid links."""
            )
            
            # Channel data cleaning agent  
            self.agents['channel'] = Agent(
                model=model,
                result_type=CleanedChannelData,
                system_prompt="""You are an expert at cleaning and validating YouTube channel data.

Your tasks:
1. Clean channel names (remove extra formatting, fix capitalization)
2. Validate subscriber counts (check for reasonable ranges, parse K/M/B notation)
3. Clean channel descriptions (remove HTML, fix encoding issues)
4. Identify verification status from various indicators
5. Flag unrealistic metrics or suspicious data

Subscriber count validation:
- Parse "1.2M" as 1,200,000
- Parse "500K" as 500,000  
- Flag counts over 100M as needing verification
- Set 0 for unparseable counts

Be conservative with validation - better to flag uncertain data."""
            )
            
            # Platform data cleaning agent
            self.agents['platform'] = Agent(
                model=model,
                result_type=CleanedPlatformData,
                system_prompt="""You are an expert at cleaning data extracted from social media platforms.

Your tasks:
1. Validate follower/subscriber counts and parse notation (K, M, B)
2. Clean bio text (remove HTML, fix encoding, preserve meaningful content)
3. Extract engagement metrics (likes, posts, etc.) when available
4. Identify verification status from badges or indicators
5. Flag suspicious metrics or bot-like behavior

Data validation rules:
- Follower counts should be reasonable for the platform
- Bio text should be meaningful, not HTML/CSS
- Engagement should align with follower count
- Verification indicators vary by platform

Focus on data quality and realistic metrics."""
            )
            
            logger.info("✅ AI Data Cleaner initialized with all specialized agents")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AI Data Cleaner: {e}")
            self.agents = {}
    
    async def clean_artist_name(self, title: str, raw_extracted_name: str = None) -> Optional[CleanedArtistData]:
        """
        Clean artist name from video title using AI.
        
        Args:
            title: Original video title
            raw_extracted_name: Previously extracted name (if any)
            
        Returns:
            Cleaned artist data or None if cleaning fails
        """
        if 'artist' not in self.agents:
            return None
            
        try:
            prompt = f"""Clean the artist name from this YouTube video title:

Title: "{title}"
"""
            if raw_extracted_name:
                prompt += f"""
Previously extracted name: "{raw_extracted_name}"
"""
            
            prompt += """
Return the clean primary artist name with confidence score."""

            result = await asyncio.wait_for(
                self.agents['artist'].run(prompt),
                timeout=10.0
            )
            
            if result.data.confidence_score >= 0.7:
                logger.info(f"🤖 AI cleaned artist: '{result.data.artist_name}' (confidence: {result.data.confidence_score:.2f})")
                return result.data
            else:
                logger.warning(f"⚠️ Low confidence artist cleaning: {result.data.confidence_score:.2f}")
                return result.data  # Return anyway but with low confidence flag
                
        except Exception as e:
            logger.error(f"❌ Artist name cleaning failed: {e}")
            return None
    
    async def clean_social_links(self, raw_links: Dict[str, str]) -> Optional[CleanedSocialLinks]:
        """
        Clean and validate social media links using AI.
        
        Args:
            raw_links: Dictionary of platform -> URL mappings
            
        Returns:
            Cleaned social links or None if cleaning fails
        """
        if 'social' not in self.agents or not raw_links:
            return None
            
        try:
            links_text = "\n".join([f"{platform}: {url}" for platform, url in raw_links.items()])
            
            prompt = f"""Clean and validate these social media links:

{links_text}

Validate URLs, fix formatting issues, and ensure they point to legitimate artist profiles.
Remove any suspicious or invalid links."""

            result = await asyncio.wait_for(
                self.agents['social'].run(prompt),
                timeout=10.0
            )
            
            logger.info(f"🔗 AI cleaned {len([l for l in [result.data.instagram, result.data.tiktok, result.data.spotify, result.data.twitter, result.data.facebook] if l])} social links")
            return result.data
                
        except Exception as e:
            logger.error(f"❌ Social links cleaning failed: {e}")
            return None
    
    async def clean_channel_data(self, raw_data: Dict[str, Any]) -> Optional[CleanedChannelData]:
        """
        Clean YouTube channel data using AI.
        
        Args:
            raw_data: Raw channel data dictionary
            
        Returns:
            Cleaned channel data or None if cleaning fails
        """
        if 'channel' not in self.agents or not raw_data:
            return None
            
        try:
            data_text = "\n".join([f"{key}: {value}" for key, value in raw_data.items() if value])
            
            prompt = f"""Clean and validate this YouTube channel data:

{data_text}

Parse subscriber counts, clean channel names, validate descriptions, and identify verification status."""

            result = await asyncio.wait_for(
                self.agents['channel'].run(prompt),
                timeout=10.0
            )
            
            logger.info(f"📺 AI cleaned channel data: {result.data.channel_name} ({result.data.subscriber_count:,} subscribers)")
            return result.data
                
        except Exception as e:
            logger.error(f"❌ Channel data cleaning failed: {e}")
            return None
    
    async def clean_platform_data(self, platform: str, raw_data: Dict[str, Any]) -> Optional[CleanedPlatformData]:
        """
        Clean social media platform data using AI.
        
        Args:
            platform: Platform name (instagram, tiktok, spotify)
            raw_data: Raw platform data
            
        Returns:
            Cleaned platform data or None if cleaning fails
        """
        if 'platform' not in self.agents or not raw_data:
            return None
            
        try:
            data_text = "\n".join([f"{key}: {value}" for key, value in raw_data.items() if value])
            
            prompt = f"""Clean and validate this {platform} data:

{data_text}

Parse follower counts, clean bio text, extract engagement metrics, and validate data quality."""

            result = await asyncio.wait_for(
                self.agents['platform'].run(prompt),
                timeout=10.0
            )
            
            result.data.platform = platform
            logger.info(f"📱 AI cleaned {platform} data: {result.data.follower_count or 'N/A'} followers")
            return result.data
                
        except Exception as e:
            logger.error(f"❌ Platform data cleaning failed for {platform}: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if AI data cleaning is available."""
        return len(self.agents) > 0 and settings.is_deepseek_configured()
    
    async def get_cleaning_summary(self) -> Dict[str, Any]:
        """Get summary of AI cleaning capabilities."""
        return {
            "available": self.is_available(),
            "deepseek_configured": settings.is_deepseek_configured(),
            "agents_loaded": list(self.agents.keys()),
            "capabilities": [
                "Artist name extraction and cleaning",
                "Social media link validation", 
                "YouTube channel data cleaning",
                "Platform data validation and parsing",
                "Confidence scoring for all extractions"
            ]
        }


# Global instance for reuse
_ai_cleaner: Optional[AIDataCleaner] = None


def get_ai_cleaner() -> AIDataCleaner:
    """Get or create the global AI data cleaner instance."""
    global _ai_cleaner
    if _ai_cleaner is None:
        _ai_cleaner = AIDataCleaner()
    return _ai_cleaner