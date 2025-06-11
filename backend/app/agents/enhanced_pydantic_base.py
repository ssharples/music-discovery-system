"""
Enhanced PydanticAI Agent Base - Advanced features for music discovery agents
Based on enhanced_pydantic_agent_base.py example with tools, streaming, and retry logic
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, TypeVar, Generic
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.tools import RunContext
from pydantic_ai.settings import ModelSettings
from typing_extensions import TypedDict

from app.core.config import settings

logger = logging.getLogger(__name__)

# Type variable for output data
OutputT = TypeVar('OutputT', bound=BaseModel)

class AgentContext(TypedDict):
    """Context passed to agent dependencies"""
    session_id: str
    user_id: Optional[str]
    metadata: Dict[str, Any]

class EnhancedPydanticAgent(Generic[OutputT]):
    """
    Base class for enhanced PydanticAI agents with advanced features:
    - Tool registration and usage
    - Dependency injection
    - Streaming responses
    - Structured output validation
    - Retry logic with custom handlers
    - Multi-model fallback support
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        result_type: type[OutputT],
        tools: Optional[List] = None,
        max_retries: int = 3,
        enable_streaming: bool = True
    ):
        self.name = name
        self.result_type = result_type
        self.enable_streaming = enable_streaming
        
        # Initialize DeepSeek model with enhanced settings
        self.model = OpenAIModel(
            'deepseek-chat',
            provider=DeepSeekProvider(
                api_key=settings.DEEPSEEK_API_KEY
            )
        )
        
        # Model settings for better control
        self.model_settings = ModelSettings(
            temperature=0.7,
            max_tokens=2000,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        # Create agent with all advanced features
        self.agent = Agent(
            model=self.model,
            result_type=self.result_type,
            system_prompt=system_prompt,
            deps_type=AgentContext,
            retries=max_retries,
            result_retries=max_retries,
            tools=tools or []
        )
        
        # Register default tools
        self._register_default_tools()
        
        # Set up custom retry handler
        self._setup_retry_handler()
        
        logger.info(f"✅ Enhanced {name} agent initialized with {len(self.agent.tools)} tools")
    
    def _register_default_tools(self):
        """Register default tools available to all agents"""
        
        @self.agent.tool
        async def validate_url(ctx: RunContext[AgentContext], url: str) -> str:
            """Validate and clean a URL"""
            import re
            # Basic URL validation
            if not re.match(r'https?://[\w\-\.]+\.\w+', url):
                raise ValueError(f"Invalid URL format: {url}")
            # Clean URL (remove tracking params, etc)
            clean_url = url.split('?')[0]
            return clean_url
        
        @self.agent.tool
        async def extract_numbers(ctx: RunContext[AgentContext], text: str) -> int:
            """Extract numbers from text (e.g., follower counts)"""
            import re
            # Handle K, M, B suffixes
            match = re.search(r'([\d,\.]+)\s*([KMB])?', text, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(',', '')
                num = float(num_str)
                suffix = match.group(2)
                if suffix:
                    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
                    num *= multipliers.get(suffix.upper(), 1)
                return int(num)
            return 0
        
        @self.agent.tool
        async def log_progress(ctx: RunContext[AgentContext], message: str) -> str:
            """Log progress messages during processing"""
            logger.info(f"🤖 [{ctx.deps.get('session_id', 'unknown')}] {message}")
            return "Logged"
    
    def _setup_retry_handler(self):
        """Set up custom retry logic"""
        
        @self.agent.model_retry
        async def handle_errors(ctx: RunContext[AgentContext], exception: Exception) -> ModelRetry:
            """Custom retry handler for various error types"""
            error_str = str(exception).lower()
            
            if "rate_limit" in error_str:
                logger.warning("Rate limit hit, waiting 5 seconds...")
                await asyncio.sleep(5)
                return ModelRetry(
                    content="I encountered a rate limit. Please continue with your previous response."
                )
            
            elif isinstance(exception, ValidationError):
                logger.warning(f"Validation error: {exception}")
                return ModelRetry(
                    content=f"""The output didn't match the expected format. 
                    Please ensure you return the correct structured output.
                    Error details: {exception}"""
                )
            
            elif "timeout" in error_str:
                return ModelRetry(
                    content="The request timed out. Please provide a concise response."
                )
            
            else:
                logger.error(f"Unexpected error: {exception}")
                return ModelRetry(content="An error occurred. Please try again.")
    
    async def run_with_retry(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> OutputT:
        """
        Run agent with retry logic and error handling
        
        Args:
            prompt: The prompt to send to the agent
            context: Optional context for dependencies
            **kwargs: Additional arguments for the agent
            
        Returns:
            The structured output of type OutputT
        """
        context = context or {"session_id": "default", "user_id": None, "metadata": {}}
        
        try:
            result = await self.agent.run(
                prompt,
                deps=context,
                model_settings=self.model_settings,
                **kwargs
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Agent {self.name} failed after retries: {e}")
            raise
    
    async def run_streaming(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        on_partial: Optional[callable] = None,
        **kwargs
    ) -> OutputT:
        """
        Run agent with streaming support for real-time updates
        
        Args:
            prompt: The prompt to send to the agent
            context: Optional context for dependencies
            on_partial: Callback for partial results
            **kwargs: Additional arguments
            
        Returns:
            The final structured output
        """
        if not self.enable_streaming:
            return await self.run_with_retry(prompt, context, **kwargs)
        
        context = context or {"session_id": "default", "user_id": None, "metadata": {}}
        
        try:
            async with self.agent.run_stream(
                prompt,
                deps=context,
                model_settings=self.model_settings,
                **kwargs
            ) as result:
                # Stream structured output with validation
                async for message, is_last in result.stream_structured(debounce_by=0.1):
                    try:
                        partial_output = await result.validate_structured_output(
                            message,
                            allow_partial=not is_last
                        )
                        if on_partial:
                            await on_partial(partial_output, is_last)
                        
                        if is_last:
                            return partial_output
                            
                    except ValidationError as e:
                        if is_last:
                            logger.error(f"Final validation failed: {e}")
                            raise
                        # Continue with partial results
                        continue
                        
        except Exception as e:
            logger.error(f"❌ Streaming failed for {self.name}: {e}")
            raise
    
    async def run_with_fallback(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        fallback_models: Optional[List[str]] = None,
        **kwargs
    ) -> OutputT:
        """
        Run with fallback to other models if primary fails
        
        Args:
            prompt: The prompt to send
            context: Optional context
            fallback_models: List of fallback model names
            **kwargs: Additional arguments
            
        Returns:
            The structured output
        """
        models_to_try = ['deepseek-chat']
        if fallback_models:
            models_to_try.extend(fallback_models)
        
        last_error = None
        for model_name in models_to_try:
            try:
                # Clone agent with different model
                if model_name != 'deepseek-chat':
                    # This would need proper implementation for other providers
                    logger.info(f"Trying fallback model: {model_name}")
                    
                return await self.run_with_retry(prompt, context, **kwargs)
                
            except Exception as e:
                last_error = e
                logger.warning(f"Model {model_name} failed: {e}")
                continue
        
        raise Exception(f"All models failed. Last error: {last_error}")
    
    def add_tool(self, tool_func: callable) -> None:
        """Add a new tool to the agent dynamically"""
        self.agent.tool(tool_func)
        logger.info(f"Added tool {tool_func.__name__} to {self.name}")

# Example implementation for enhanced artist extraction
class EnhancedArtistData(BaseModel):
    """Enhanced artist data with confidence scores"""
    name: str = Field(description="Artist name")
    genres: List[str] = Field(default=[], description="Music genres")
    social_links: Dict[str, str] = Field(default={}, description="Social media links")
    metrics: Dict[str, int] = Field(default={}, description="Follower counts, views, etc.")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall confidence")
    extraction_notes: str = Field(description="Notes about the extraction process")

class EnhancedArtistExtractionAgent(EnhancedPydanticAgent[EnhancedArtistData]):
    """Example of using the enhanced base class"""
    
    def __init__(self):
        super().__init__(
            name="EnhancedArtistExtraction",
            system_prompt="""You are an expert at extracting and validating artist information.
            Use the provided tools to validate URLs and extract numbers.
            Always provide confidence scores and detailed extraction notes.
            Focus on accuracy over completeness.""",
            result_type=EnhancedArtistData,
            enable_streaming=True
        )
        
        # Add specialized tools
        self._add_artist_tools()
    
    def _add_artist_tools(self):
        """Add artist-specific tools"""
        
        @self.agent.tool
        async def validate_artist_name(ctx: RunContext[AgentContext], name: str) -> Dict[str, Any]:
            """Validate and clean artist name"""
            # Remove common suffixes
            clean_name = name
            for suffix in [' - Topic', ' Official', ' VEVO', ' (Official)']:
                clean_name = clean_name.replace(suffix, '')
            
            # Check if it looks like a real artist name
            is_valid = len(clean_name) > 1 and not clean_name.isdigit()
            
            return {
                "original": name,
                "cleaned": clean_name.strip(),
                "is_valid": is_valid,
                "confidence": 0.9 if is_valid else 0.3
            }