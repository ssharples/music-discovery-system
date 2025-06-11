"""
Enhanced Crawl4AI Base - Advanced web scraping with LLM integration
"""
import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.models import CrawlResult
from crawl4ai.extraction_strategy import (
    JsonCssExtractionStrategy, 
    LLMExtractionStrategy
)
from crawl4ai.content_filter import LLMContentFilter
from crawl4ai.llm_config import LLMConfig
from crawl4ai.markdown_generator import DefaultMarkdownGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)

class EnhancedCrawl4AIBase(ABC):
    """
    Enhanced base class for Crawl4AI agents with advanced features:
    - LLM-based content filtering
    - Advanced JavaScript interactions
    - Multiple extraction strategies
    - Session management
    - Anti-bot measures
    - Content quality validation
    """
    
    def __init__(self, name: str):
        self.name = name
        self.sessions = {}  # session_id -> page session
        
        # Enhanced browser configurations
        self.browser_configs = {
            'default': BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080,
                java_script_enabled=True,
                ignore_https_errors=True
            ),
            'stealth': BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080,
                user_agent=self._get_random_user_agent(),
                extra_args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--disable-setuid-sandbox"
                ]
            ),
            'mobile': BrowserConfig(
                headless=True,
                viewport_width=375,
                viewport_height=667,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
            )
        }
        
        # LLM configuration for content filtering
        self.llm_config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=0.3,
            max_tokens=1000
        )
        
        logger.info(f"✅ Enhanced {name} Crawl4AI agent initialized")
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent for anti-bot measures"""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
        return random.choice(agents)
    
    async def create_llm_content_filter(self, instruction: str) -> LLMContentFilter:
        """
        Create an LLM-based content filter for intelligent extraction
        
        Args:
            instruction: Natural language instruction for content filtering
            
        Returns:
            Configured LLM content filter
        """
        return LLMContentFilter(
            llm_config=self.llm_config,
            instruction=instruction,
            chunk_token_threshold=500,
            verbose=True
        )
    
    async def create_llm_extraction_strategy(
        self,
        schema: Dict[str, Any],
        instruction: str
    ) -> LLMExtractionStrategy:
        """
        Create LLM-based extraction strategy for complex content
        
        Args:
            schema: Pydantic model or dict schema for extraction
            instruction: Natural language extraction instructions
            
        Returns:
            Configured LLM extraction strategy
        """
        return LLMExtractionStrategy(
            llm_config=self.llm_config,
            schema=schema,
            instruction=instruction,
            verbose=True
        )
    
    async def create_advanced_crawler_config(
        self,
        extraction_type: str = "css",
        extraction_config: Optional[Dict[str, Any]] = None,
        js_code: Optional[Union[str, List[str]]] = None,
        wait_for: Optional[str] = None,
        session_id: Optional[str] = None,
        enable_magic: bool = True,
        scan_full_page: bool = True
    ) -> CrawlerRunConfig:
        """
        Create advanced crawler configuration with all features
        
        Args:
            extraction_type: Type of extraction ("css", "llm", "hybrid")
            extraction_config: Configuration for extraction strategy
            js_code: JavaScript to execute
            wait_for: Wait condition (CSS selector or JS function)
            session_id: Session ID for persistent sessions
            enable_magic: Enable magic mode for anti-bot
            scan_full_page: Scan entire page with scrolling
            
        Returns:
            Configured CrawlerRunConfig
        """
        # Create extraction strategy based on type
        extraction_strategy = None
        if extraction_config:
            if extraction_type == "css":
                extraction_strategy = JsonCssExtractionStrategy(extraction_config)
            elif extraction_type == "llm":
                extraction_strategy = await self.create_llm_extraction_strategy(
                    extraction_config.get("schema", {}),
                    extraction_config.get("instruction", "")
                )
            elif extraction_type == "hybrid":
                # Combine CSS and LLM strategies
                css_strategy = JsonCssExtractionStrategy(extraction_config.get("css_schema", {}))
                llm_strategy = await self.create_llm_extraction_strategy(
                    extraction_config.get("llm_schema", {}),
                    extraction_config.get("llm_instruction", "")
                )
                # Would need custom implementation to combine
                extraction_strategy = css_strategy  # Fallback for now
        
        # Create content filter if instruction provided
        content_filter = None
        if extraction_config and extraction_config.get("filter_instruction"):
            content_filter = await self.create_llm_content_filter(
                extraction_config["filter_instruction"]
            )
        
        # Create markdown generator with filter
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={"ignore_links": False}
        ) if content_filter else None
        
        return CrawlerRunConfig(
            # Core settings
            cache_mode=CacheMode.BYPASS,
            verbose=True,
            
            # Extraction
            extraction_strategy=extraction_strategy,
            markdown_generator=markdown_generator,
            
            # JavaScript and waiting
            js_code=js_code,
            wait_for=wait_for,
            wait_until="domcontentloaded",
            delay_before_return_html=3.0,
            
            # Page interaction
            page_timeout=30000,
            scroll_delay=1.0,
            
            # Anti-bot features
            magic=enable_magic,
            simulate_user=True,
            override_navigator=True,
            remove_overlay_elements=True,
            
            # Content settings
            scan_full_page=scan_full_page,
            excluded_tags=["script", "style", "nav", "footer"],
            word_count_threshold=10,
            
            # Session management
            session_id=session_id,
            
            # Media handling
            wait_for_images=False,
            screenshot=False,
            pdf=False
        )
    
    async def crawl_with_session(
        self,
        url: str,
        session_id: str,
        js_interactions: List[Dict[str, Any]],
        extraction_config: Optional[Dict[str, Any]] = None,
        browser_type: str = "default"
    ) -> CrawlResult:
        """
        Crawl with persistent session and multiple interactions
        
        Args:
            url: URL to crawl
            session_id: Session identifier
            js_interactions: List of JS interactions to perform
            extraction_config: Extraction configuration
            browser_type: Browser configuration type
            
        Returns:
            CrawlResult with extracted data
        """
        browser_config = self.browser_configs.get(browser_type, self.browser_configs['default'])
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = []
            
            for i, interaction in enumerate(js_interactions):
                # Prepare JS code
                js_code = interaction.get("js_code", "")
                wait_for = interaction.get("wait_for")
                delay = interaction.get("delay", 2.0)
                
                # Create config for this interaction
                config = await self.create_advanced_crawler_config(
                    extraction_type=interaction.get("extraction_type", "css"),
                    extraction_config=extraction_config if i == len(js_interactions) - 1 else None,
                    js_code=js_code,
                    wait_for=wait_for,
                    session_id=session_id,
                    enable_magic=True
                )
                
                # Add delay between interactions
                if i > 0:
                    await asyncio.sleep(delay)
                
                # Execute crawl
                result = await crawler.arun(
                    url=url,
                    config=config
                )
                
                results.append(result)
                
                if not result.success:
                    logger.error(f"Interaction {i+1} failed: {result.error_message}")
                    break
            
            # Return the last result with all accumulated data
            return results[-1] if results else None
    
    async def crawl_with_pagination(
        self,
        base_url: str,
        max_pages: int = 5,
        next_page_selector: str = "a.next-page",
        extraction_config: Optional[Dict[str, Any]] = None
    ) -> List[CrawlResult]:
        """
        Crawl multiple pages with pagination support
        
        Args:
            base_url: Starting URL
            max_pages: Maximum pages to crawl
            next_page_selector: CSS selector for next page link
            extraction_config: Extraction configuration
            
        Returns:
            List of CrawlResults from all pages
        """
        results = []
        current_url = base_url
        session_id = f"pagination_{hash(base_url)}"
        
        for page_num in range(max_pages):
            logger.info(f"Crawling page {page_num + 1}: {current_url}")
            
            # JavaScript to find and extract next page URL
            js_find_next = f"""
            const nextLink = document.querySelector('{next_page_selector}');
            if (nextLink) {{
                window.__next_page_url = nextLink.href;
            }}
            """
            
            config = await self.create_advanced_crawler_config(
                extraction_type="css",
                extraction_config=extraction_config,
                js_code=js_find_next,
                session_id=session_id,
                scan_full_page=True
            )
            
            async with AsyncWebCrawler(config=self.browser_configs['stealth']) as crawler:
                result = await crawler.arun(url=current_url, config=config)
                
                if not result.success:
                    logger.error(f"Failed to crawl page {page_num + 1}")
                    break
                
                results.append(result)
                
                # Check for next page URL in JavaScript context
                if result.js_result and "__next_page_url" in result.js_result:
                    current_url = result.js_result["__next_page_url"]
                else:
                    logger.info("No more pages found")
                    break
                
                # Rate limiting
                await asyncio.sleep(random.uniform(2, 4))
        
        return results
    
    async def crawl_with_infinite_scroll(
        self,
        url: str,
        target_items: int = 100,
        item_selector: str = ".item",
        extraction_config: Optional[Dict[str, Any]] = None
    ) -> CrawlResult:
        """
        Handle infinite scroll pages
        
        Args:
            url: URL to crawl
            target_items: Target number of items to load
            item_selector: CSS selector for items
            extraction_config: Extraction configuration
            
        Returns:
            CrawlResult with all loaded content
        """
        # Advanced infinite scroll handling
        js_infinite_scroll = f"""
        (async function() {{
            let previousHeight = 0;
            let currentHeight = document.body.scrollHeight;
            let scrollAttempts = 0;
            const maxAttempts = 20;
            
            while (scrollAttempts < maxAttempts) {{
                // Count current items
                const items = document.querySelectorAll('{item_selector}');
                console.log(`Found ${{items.length}} items`);
                
                if (items.length >= {target_items}) {{
                    console.log('Target reached');
                    break;
                }}
                
                // Scroll strategies
                window.scrollTo(0, currentHeight);
                window.scrollBy(0, 500);
                
                // Trigger scroll events
                window.dispatchEvent(new Event('scroll'));
                document.dispatchEvent(new Event('scroll'));
                
                // Wait for content to load
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                previousHeight = currentHeight;
                currentHeight = document.body.scrollHeight;
                
                if (currentHeight === previousHeight) {{
                    // Try alternative scroll methods
                    const scrollContainer = document.querySelector('.scroll-container') || document.body;
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                    
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    currentHeight = document.body.scrollHeight;
                    if (currentHeight === previousHeight) {{
                        console.log('No more content loading');
                        break;
                    }}
                }}
                
                scrollAttempts++;
            }}
            
            // Final count
            const finalItems = document.querySelectorAll('{item_selector}');
            console.log(`Final count: ${{finalItems.length}} items`);
        }})();
        """
        
        config = await self.create_advanced_crawler_config(
            extraction_type="css",
            extraction_config=extraction_config,
            js_code=js_infinite_scroll,
            wait_for=f"css:{item_selector}:nth-child({min(target_items, 50)})",
            scan_full_page=True,
            enable_magic=True
        )
        
        # Increase timeouts for infinite scroll
        config.page_timeout = 60000
        config.delay_before_return_html = 5.0
        
        async with AsyncWebCrawler(config=self.browser_configs['stealth']) as crawler:
            return await crawler.arun(url=url, config=config)
    
    @abstractmethod
    async def extract_data(self, html: str, url: str) -> Dict[str, Any]:
        """
        Abstract method to be implemented by specific agents
        
        Args:
            html: Page HTML content
            url: Page URL
            
        Returns:
            Extracted data dictionary
        """
        pass 