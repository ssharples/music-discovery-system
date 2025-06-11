"""
Enhanced AI Data Cleaner Example - Demonstrates PydanticAI advanced features
This is an example implementation showing how to upgrade the existing AI Data Cleaner
"""
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.tools import RunContext
from typing_extensions import TypedDict

from app.core.config import settings
from app.api.websocket import notify_cleaning_progress

logger = logging.getLogger(__name__)


class CleanerContext(TypedDict):
    """Context for cleaner agent dependencies"""
    session_id: str
    artist_id: Optional[str]
    platform: Optional[str]
    metadata: Dict[str, Any]


class EnhancedCleanedArtistData(BaseModel):
    """Enhanced cleaned artist data with confidence scores"""
    artist_name: str = Field(description="Clean artist name without featured artists")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in extraction")
    featured_artists: List[str] = Field(default=[], description="Featured artists if any")
    is_collaboration: bool = Field(default=False)
    reasoning: str = Field(description="Explanation of cleaning decisions")
    validation_flags: Dict[str, bool] = Field(default={}, description="Validation results")
    tool_usage: List[str] = Field(default=[], description="Tools used in cleaning")


class EnhancedAIDataCleaner:
    """
    Enhanced AI Data Cleaner with PydanticAI advanced features:
    - Tool registration and usage
    - Streaming support
    - Custom retry logic
    - Dependency injection
    """
    
    def __init__(self):
        """Initialize enhanced cleaner with all features"""
        if not settings.is_deepseek_configured():
            raise ValueError("DeepSeek API key not configured")
        
        # Initialize model
        self.model = OpenAIModel(
            'deepseek-chat',
            provider=DeepSeekProvider(
                api_key=settings.DEEPSEEK_API_KEY
            )
        )
        
        # Create agent with advanced configuration
        self.agent = Agent(
            model=self.model,
            result_type=EnhancedCleanedArtistData,
            deps_type=CleanerContext,
            system_prompt="""You are an expert at cleaning and validating artist names from various sources.

Your responsibilities:
1. Extract the PRIMARY artist name (remove featured artists)
2. Use provided tools to validate URLs, parse numbers, and check data
3. Provide confidence scores based on validation results
4. Document your reasoning and which tools you used
5. Flag any suspicious or low-quality data

Always use the available tools when processing data. Be thorough but efficient.""",
            retries=3
        )
        
        # Register tools
        self._register_tools()
        
        # Set up custom retry handler
        self._setup_retry_handler()
        
        logger.info(f"✅ Enhanced AI Data Cleaner initialized with {len(self.agent.tools)} tools")
    
    def _register_tools(self):
        """Register all available tools for the agent"""
        
        @self.agent.tool
        async def validate_url(ctx: RunContext[CleanerContext], url: str) -> Dict[str, Any]:
            """Validate and clean a URL"""
            import urllib.parse
            
            try:
                parsed = urllib.parse.urlparse(url)
                
                # Check if URL is valid
                is_valid = all([parsed.scheme, parsed.netloc])
                
                # Clean URL (remove tracking params)
                if is_valid:
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.path.endswith('/'):
                        clean_url = clean_url[:-1]
                else:
                    clean_url = url
                
                # Detect platform
                platform = None
                if 'instagram.com' in parsed.netloc:
                    platform = 'instagram'
                elif 'tiktok.com' in parsed.netloc:
                    platform = 'tiktok'
                elif 'spotify.com' in parsed.netloc:
                    platform = 'spotify'
                elif 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                    platform = 'youtube'
                
                return {
                    "original": url,
                    "cleaned": clean_url,
                    "is_valid": is_valid,
                    "platform": platform,
                    "has_tracking": '?' in url or '&' in url
                }
            except Exception as e:
                return {
                    "original": url,
                    "cleaned": url,
                    "is_valid": False,
                    "error": str(e)
                }
        
        @self.agent.tool
        async def parse_follower_count(ctx: RunContext[CleanerContext], text: str) -> Dict[str, Any]:
            """Parse follower counts with K/M/B notation"""
            try:
                # Remove non-numeric characters except K, M, B
                clean_text = re.sub(r'[^\d.,KMBkmb]', '', text)
                
                # Extract number and suffix
                match = re.match(r'([\d,.]+)\s*([KMBkmb])?', clean_text)
                
                if match:
                    num_str = match.group(1).replace(',', '.')
                    num = float(num_str)
                    suffix = match.group(2)
                    
                    if suffix:
                        multipliers = {
                            'K': 1_000, 'k': 1_000,
                            'M': 1_000_000, 'm': 1_000_000,
                            'B': 1_000_000_000, 'b': 1_000_000_000
                        }
                        num *= multipliers.get(suffix, 1)
                    
                    return {
                        "original": text,
                        "parsed_value": int(num),
                        "is_valid": True,
                        "confidence": 0.9 if suffix else 1.0
                    }
                else:
                    return {
                        "original": text,
                        "parsed_value": 0,
                        "is_valid": False,
                        "error": "Could not parse number"
                    }
                    
            except Exception as e:
                return {
                    "original": text,
                    "parsed_value": 0,
                    "is_valid": False,
                    "error": str(e)
                }
        
        @self.agent.tool
        async def extract_featured_artists(ctx: RunContext[CleanerContext], title: str) -> Dict[str, Any]:
            """Extract featured artists from a title"""
            featured_patterns = [
                r'(?:ft\.?|feat\.?|featuring)\s+([^,\-\(\)]+)',
                r'(?:with|w\/)\s+([^,\-\(\)]+)',
                r'\((?:ft\.?|feat\.?|featuring)\s+([^)]+)\)',
                r'&\s+([^,\-\(\)]+)',
                r'x\s+([^,\-\(\)]+)'  # For collaborations
            ]
            
            featured_artists = []
            is_collaboration = False
            
            for pattern in featured_patterns:
                matches = re.findall(pattern, title, re.IGNORECASE)
                for match in matches:
                    artists = [a.strip() for a in re.split(r'[,&]', match)]
                    featured_artists.extend(artists)
                    
                    if 'x ' in title.lower():
                        is_collaboration = True
            
            # Clean the main title
            clean_title = title
            for pattern in featured_patterns:
                clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
            
            # Extract main artist (before - or |)
            main_artist = re.split(r'[-|]', clean_title)[0].strip()
            
            return {
                "main_artist": main_artist,
                "featured_artists": list(set(featured_artists)),
                "is_collaboration": is_collaboration,
                "original_title": title
            }
        
        @self.agent.tool
        async def validate_artist_name(ctx: RunContext[CleanerContext], name: str) -> Dict[str, Any]:
            """Validate if a name looks like a real artist name"""
            # Remove common suffixes
            suffixes_to_remove = [
                ' - Topic', ' Official', ' VEVO', ' (Official)',
                ' Music', ' Channel', ' Artist', ' Records'
            ]
            
            clean_name = name
            for suffix in suffixes_to_remove:
                clean_name = clean_name.replace(suffix, '')
            
            clean_name = clean_name.strip()
            
            # Validation checks
            validations = {
                "has_letters": bool(re.search(r'[a-zA-Z]', clean_name)),
                "not_just_numbers": not clean_name.isdigit(),
                "reasonable_length": 1 < len(clean_name) < 50,
                "no_urls": not bool(re.search(r'https?://', clean_name)),
                "no_email": not bool(re.search(r'@', clean_name)),
                "not_generic": clean_name.lower() not in ['unknown', 'various', 'anonymous', 'user']
            }
            
            confidence = sum(validations.values()) / len(validations)
            
            return {
                "original": name,
                "cleaned": clean_name,
                "is_valid": confidence > 0.7,
                "confidence": confidence,
                "validations": validations
            }
        
        @self.agent.tool
        async def log_cleaning_progress(ctx: RunContext[CleanerContext], message: str) -> str:
            """Log progress during cleaning"""
            logger.info(f"🤖 [{ctx.deps['session_id']}] {message}")
            
            # Send WebSocket notification if session_id provided
            if ctx.deps.get('session_id'):
                await notify_cleaning_progress({
                    "session_id": ctx.deps['session_id'],
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            return "Progress logged"
    
    def _setup_retry_handler(self):
        """Set up custom retry logic"""
        
        @self.agent.model_retry
        async def handle_cleaning_errors(ctx: RunContext[CleanerContext], exception: Exception) -> ModelRetry:
            """Custom retry handler for various error types"""
            error_str = str(exception).lower()
            
            if "rate_limit" in error_str:
                logger.warning("Rate limit hit, waiting 5 seconds...")
                await asyncio.sleep(5)
                return ModelRetry(
                    content="I encountered a rate limit. Please continue with the cleaning process."
                )
            
            elif isinstance(exception, ValidationError):
                logger.warning(f"Validation error: {exception}")
                return ModelRetry(
                    content=f"""The output didn't match the expected format. 
                    Please ensure you return an EnhancedCleanedArtistData object with:
                    - artist_name (string)
                    - confidence_score (float between 0 and 1)
                    - featured_artists (list of strings)
                    - is_collaboration (boolean)
                    - reasoning (string explaining your decisions)
                    - validation_flags (dict of validation results)
                    - tool_usage (list of tools you used)
                    
                    Error details: {exception}"""
                )
            
            elif "timeout" in error_str:
                return ModelRetry(
                    content="The request timed out. Please provide a concise response."
                )
            
            else:
                logger.error(f"Unexpected error in cleaning: {exception}")
                return ModelRetry(
                    content="An error occurred. Please try the cleaning process again."
                )
    
    async def clean_artist_name(
        self,
        title: str,
        context: Optional[CleanerContext] = None,
        stream_progress: bool = False
    ) -> Optional[EnhancedCleanedArtistData]:
        """
        Clean artist name with optional streaming
        
        Args:
            title: Video title or text containing artist name
            context: Optional context with session info
            stream_progress: Whether to stream partial results
            
        Returns:
            Cleaned artist data or None if cleaning fails
        """
        if not context:
            context = {
                "session_id": f"clean_{datetime.utcnow().timestamp()}",
                "artist_id": None,
                "platform": None,
                "metadata": {}
            }
        
        prompt = f"""Clean and extract the artist name from this title:

Title: "{title}"

Use the available tools to:
1. Extract featured artists using extract_featured_artists
2. Validate the artist name using validate_artist_name
3. Log your progress using log_cleaning_progress

Provide a thorough analysis with confidence scoring."""

        try:
            if stream_progress:
                # Use streaming for real-time updates
                return await self._clean_with_streaming(prompt, context)
            else:
                # Regular non-streaming execution
                result = await self.agent.run(
                    prompt,
                    deps=context
                )
                return result.data
                
        except Exception as e:
            logger.error(f"❌ Artist cleaning failed: {e}")
            return None
    
    async def _clean_with_streaming(
        self,
        prompt: str,
        context: CleanerContext
    ) -> Optional[EnhancedCleanedArtistData]:
        """Clean with streaming support for real-time updates"""
        final_result = None
        
        try:
            async with self.agent.run_stream(
                prompt,
                deps=context
            ) as result:
                async for partial, is_last in result.stream_structured(debounce_by=0.1):
                    try:
                        cleaned = await result.validate_structured_output(
                            partial,
                            allow_partial=not is_last
                        )
                        
                        # Send progress update via WebSocket
                        await notify_cleaning_progress({
                            "session_id": context['session_id'],
                            "partial_result": {
                                "artist_name": cleaned.artist_name if hasattr(cleaned, 'artist_name') else None,
                                "confidence": cleaned.confidence_score if hasattr(cleaned, 'confidence_score') else None,
                                "is_final": is_last
                            },
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        if is_last:
                            final_result = cleaned
                            
                    except ValidationError as e:
                        if is_last:
                            logger.error(f"Final validation failed: {e}")
                            raise
                        # Continue with partial results
                        continue
                        
        except Exception as e:
            logger.error(f"❌ Streaming failed: {e}")
            return None
        
        return final_result
    
    async def clean_social_links(
        self,
        raw_links: Dict[str, str],
        context: Optional[CleanerContext] = None
    ) -> Dict[str, Any]:
        """
        Clean and validate social media links
        
        Args:
            raw_links: Dictionary of platform -> URL
            context: Optional context
            
        Returns:
            Cleaned and validated links
        """
        if not context:
            context = {
                "session_id": f"links_{datetime.utcnow().timestamp()}",
                "artist_id": None,
                "platform": "multi",
                "metadata": {"link_count": len(raw_links)}
            }
        
        links_text = "\n".join([f"{platform}: {url}" for platform, url in raw_links.items()])
        
        prompt = f"""Clean and validate these social media links:

{links_text}

Use the validate_url tool for each link and provide:
1. Cleaned URLs
2. Validation status
3. Platform detection
4. Overall confidence score"""

        try:
            result = await self.agent.run(prompt, deps=context)
            return {
                "cleaned_links": result.data.validation_flags,
                "confidence": result.data.confidence_score,
                "tools_used": result.data.tool_usage
            }
        except Exception as e:
            logger.error(f"❌ Link cleaning failed: {e}")
            return {"error": str(e)}


# Example usage
async def example_usage():
    """Example of using the enhanced cleaner"""
    cleaner = EnhancedAIDataCleaner()
    
    # Example 1: Clean artist name with streaming
    title = "Dua Lipa - Levitating ft. DaBaby (Official Music Video)"
    
    print("Cleaning with streaming...")
    result = await cleaner.clean_artist_name(
        title=title,
        context={
            "session_id": "example_session",
            "artist_id": None,
            "platform": "youtube",
            "metadata": {"source": "youtube_search"}
        },
        stream_progress=True
    )
    
    if result:
        print(f"Artist: {result.artist_name}")
        print(f"Featured: {result.featured_artists}")
        print(f"Confidence: {result.confidence_score}")
        print(f"Tools used: {result.tool_usage}")
        print(f"Reasoning: {result.reasoning}")
    
    # Example 2: Clean social links
    links = {
        "instagram": "https://instagram.com/dualipa?utm_source=youtube",
        "spotify": "https://open.spotify.com/artist/6M2wZ9GZgrQXHCFfjv46we",
        "tiktok": "https://tiktok.com/@dualipa"
    }
    
    print("\nCleaning social links...")
    cleaned = await cleaner.clean_social_links(links)
    print(f"Cleaned links: {cleaned}")


if __name__ == "__main__":
    asyncio.run(example_usage()) 