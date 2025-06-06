"""
Enhanced PydanticAI Agent Base with modern patterns and tools integration.
"""
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.tools import Tool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union, Callable
import logging
from datetime import datetime
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.dependencies import PipelineDependencies

logger = logging.getLogger(__name__)

class AgentContext(BaseModel):
    """Structured context for agent operations"""
    session_id: str
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentResponse(BaseModel):
    """Standardized agent response structure"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time: Optional[float] = None

class EnhancedAgentBase(ABC):
    """
    Enhanced base class for PydanticAI agents with modern patterns:
    - Structured tools with proper typing
    - Dependencies injection
    - Error handling and retries
    - Performance monitoring
    - Caching integration
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._agent: Optional[Agent] = None
        self._tools: List[Tool] = []
        self._initialized = False
        logger.info(f"🤖 Initializing {agent_name} with enhanced patterns")
    
    @property
    def agent(self) -> Optional[Agent]:
        """Lazy initialization of PydanticAI agent"""
        if not self._initialized:
            self._initialize_agent()
        return self._agent
    
    def _initialize_agent(self):
        """Initialize agent with proper error handling"""
        try:
            # Model selection with fallbacks
            model = self._get_model()
            if not model:
                logger.error(f"❌ Failed to initialize model for {self.agent_name}")
                return
            
            # Create agent with tools
            self._agent = Agent(
                model=model,
                system_prompt=self.get_system_prompt(),
                tools=self._get_tools(),
                deps_type=PipelineDependencies
            )
            
            self._initialized = True
            logger.info(f"✅ {self.agent_name} agent initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize {self.agent_name}: {e}")
            self._agent = None
    
    def _get_model(self) -> Optional[OpenAIModel]:
        """Get model with fallback options"""
        # Try DeepSeek first (cost-effective)
        if settings.is_deepseek_configured():
            try:
                return OpenAIModel('deepseek-chat', provider=DeepSeekProvider())
            except Exception as e:
                logger.warning(f"⚠️ DeepSeek unavailable: {e}")
        
        # Fallback to OpenAI
        if settings.OPENAI_API_KEY:
            try:
                return OpenAIModel('gpt-4o-mini')  # Cost-effective GPT-4 variant
            except Exception as e:
                logger.warning(f"⚠️ OpenAI unavailable: {e}")
        
        return None
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return system prompt for the agent"""
        pass
    
    @abstractmethod
    def _get_tools(self) -> List[Tool]:
        """Return list of tools for the agent"""
        pass
    
    async def run_with_context(
        self,
        prompt: str,
        context: AgentContext,
        deps: PipelineDependencies,
        **kwargs
    ) -> AgentResponse:
        """Run agent with structured context and error handling"""
        start_time = datetime.now()
        
        try:
            if not self.agent:
                return AgentResponse(
                    success=False,
                    error=f"{self.agent_name} agent not available"
                )
            
            # Execute with retries - pass deps directly like existing agents
            result = await self._run_with_retries(prompt, deps)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                success=True,
                data=result.data if hasattr(result, 'data') else result,
                metadata={
                    "agent": self.agent_name,
                    "context": context.model_dump(),
                    "model_usage": getattr(result, 'usage', None)
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ {self.agent_name} execution failed: {e}")
            
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={
                    "agent": self.agent_name,
                    "context": context.model_dump()
                },
                processing_time=processing_time
            )
    
    async def _run_with_retries(self, prompt: str, deps: PipelineDependencies, max_retries: int = 3):
        """Execute agent with exponential backoff retries"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                # Use the same pattern as existing agents
                result = await self.agent.run(prompt, deps=deps)
                return result
            except ModelRetry as e:
                if attempt == max_retries - 1:
                    raise e
                wait_time = 2 ** attempt
                logger.warning(f"⚠️ {self.agent_name} retry {attempt + 1}/{max_retries}, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                logger.warning(f"⚠️ {self.agent_name} attempt {attempt + 1} failed: {e}")
        
        raise Exception(f"All retries exhausted for {self.agent_name}")

class WebScrapingTool(Tool):
    """Enhanced web scraping tool using Firecrawl integration"""
    
    async def scrape_url(self, url: str, extract_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Scrape URL with Firecrawl for clean, LLM-ready data
        
        Args:
            url: URL to scrape
            extract_schema: Optional schema for structured extraction
        """
        try:
            import firecrawl
            
            if not settings.FIRECRAWL_API_KEY:
                logger.warning("⚠️ Firecrawl API key not configured")
                return {"error": "Firecrawl not configured"}
            
            app = firecrawl.FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
            
            if extract_schema:
                # Use Firecrawl's extraction feature for structured data
                result = app.scrape_url(
                    url=url,
                    params={
                        'formats': ['extract'],
                        'extract': {
                            'schema': extract_schema
                        }
                    }
                )
            else:
                # Standard scraping for clean content
                result = app.scrape_url(
                    url=url,
                    params={
                        'formats': ['markdown', 'html']
                    }
                )
            
            return {
                "success": True,
                "data": result,
                "source": "firecrawl"
            }
            
        except Exception as e:
            logger.error(f"❌ Firecrawl scraping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "firecrawl"
            }

# Tool registry for reusable tools
class ToolRegistry:
    """Registry for managing reusable agent tools"""
    
    _tools: Dict[str, Tool] = {}
    
    @classmethod
    def register_tool(cls, name: str, tool: Tool):
        """Register a tool for reuse across agents"""
        cls._tools[name] = tool
        logger.info(f"📝 Registered tool: {name}")
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Tool]:
        """Get registered tool by name"""
        return cls._tools.get(name)
    
    @classmethod
    def get_all_tools(cls) -> List[Tool]:
        """Get all registered tools"""
        return list(cls._tools.values())

# Register common tools
ToolRegistry.register_tool("web_scraping", WebScrapingTool()) 