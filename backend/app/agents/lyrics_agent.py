# backend/app/agents/lyrics_agent.py
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import List, Dict, Any, Optional
import logging
import re
from collections import Counter
import json
import asyncio
from datetime import datetime

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import LyricAnalysis, VideoMetadata

logger = logging.getLogger(__name__)

# Factory function for on-demand agent creation
def create_lyrics_agent():
    """Create lyrics agent on-demand to avoid import-time blocking"""
    try:
        return Agent(
            model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
            output_type=LyricAnalysis,  # Structured output for validation
            system_prompt="""You are a music lyrics analyst specializing in:
            1. Identifying themes and topics in song lyrics
            2. Analyzing emotional content and sentiment
            3. Categorizing lyrical style and techniques
            4. Understanding subject matter and messaging
            
            Analyze lyrics objectively, focusing on:
            - Main themes (love, heartbreak, success, struggle, party, etc.)
            - Emotional tone (uplifting, melancholic, angry, hopeful, etc.)
            - Lyrical complexity and style
            - Target audience and messaging
            - Cultural references and context
            
            Return structured LyricAnalysis with sentiment_score (-1 to 1), themes list, and analysis metadata.
            Provide concise, insightful analysis suitable for music industry professionals.
            """
        )
    except Exception as e:
        logger.error(f"Failed to create lyrics agent: {e}")
        return None

def clean_lyrics(lyrics: str) -> str:
    """Clean and normalize lyrics text"""
    # Remove YouTube caption artifacts
    lyrics = re.sub(r'\[.*?\]', '', lyrics)  # Remove [Music], [Applause], etc.
    lyrics = re.sub(r'\(.*?\)', '', lyrics)  # Remove (instrumental), etc.
    
    # Normalize whitespace
    lyrics = ' '.join(lyrics.split())
    
    # Remove excessive repetition
    lines = lyrics.split('.')
    unique_lines = []
    for line in lines:
        if line.strip() and (not unique_lines or line.strip() != unique_lines[-1]):
            unique_lines.append(line.strip())
    
    return ' '.join(unique_lines)

class LyricsAnalysisAgent:
    """Lyrics analysis agent with lazy initialization and proper error handling"""
    
    def __init__(self):
        self._agent = None
        self._agent_creation_attempted = False
        self._cache = {}  # Simple cache for analysis results
        logger.info("LyricsAnalysisAgent initialized (agent created on-demand)")
    
    @property
    def agent(self):
        """Lazy initialization of agent"""
        if self._agent is None and not self._agent_creation_attempted:
            self._agent_creation_attempted = True
            self._agent = create_lyrics_agent()
        return self._agent
    
    async def analyze_artist_lyrics(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        videos_with_captions: List[Dict[str, Any]]
    ) -> List[LyricAnalysis]:
        """Analyze lyrics from multiple videos with proper error handling and retry logic"""
        
        logger.info(f"🎵 Analyzing lyrics for artist {artist_id} from {len(videos_with_captions)} videos")
        
        analyses = []
        
        for video in videos_with_captions:
            if not video.get('captions'):
                continue
            
            video_id = video.get('video_id') or video.get('id')
            if not video_id:
                logger.warning("Video missing ID, skipping")
                continue
            
            try:
                # Check cache first
                cache_key = f"lyrics:{video_id}"
                if cache_key in self._cache:
                    logger.info(f"📦 Using cached lyrics analysis for video {video_id}")
                    analyses.append(self._cache[cache_key])
                    continue
                
                # Analyze lyrics with retry logic
                analysis = await self._analyze_video_lyrics_with_retry(
                    deps, artist_id, video, max_retries=3
                )
                
                if analysis:
                    analyses.append(analysis)
                    # Cache the result
                    self._cache[cache_key] = analysis
                    logger.info(f"✅ Lyrics analysis completed for video {video_id}")
                else:
                    logger.warning(f"⚠️ No analysis result for video {video_id}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to analyze lyrics for video {video_id}: {e}")
                continue
        
        logger.info(f"🎯 Completed lyrics analysis: {len(analyses)} successful analyses")
        return analyses
    
    async def _analyze_video_lyrics_with_retry(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        video: Dict[str, Any],
        max_retries: int = 3
    ) -> Optional[LyricAnalysis]:
        """Analyze video lyrics with retry logic and exponential backoff"""
        
        video_id = video.get('video_id') or video.get('id')
        lyrics = video.get('captions', '')
        
        if not lyrics:
            return None
        
        # Clean and validate lyrics
        cleaned_lyrics = clean_lyrics(lyrics)
        if len(cleaned_lyrics) < 50:
            logger.info(f"📏 Insufficient lyrics content for video {video_id}")
            return None
        
        # Detect language first
        language = await self._detect_language(cleaned_lyrics)
        
        # Only analyze English content for now (configurable)
        if language != 'en':
            logger.info(f"🌍 Skipping non-English content for video {video_id} (detected: {language})")
            return None
        
        # Attempt analysis with retries
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Lyrics analysis attempt {attempt + 1} for video {video_id}")
                
                # Use AI agent if available
                if self.agent and settings.is_deepseek_configured():
                    analysis = await self._ai_lyrics_analysis(
                        deps, artist_id, video_id, cleaned_lyrics, video.get('title')
                    )
                    if analysis:
                        return analysis
                
                # Fallback to manual analysis
                analysis = await self._manual_lyrics_analysis(
                    deps, artist_id, video_id, cleaned_lyrics, video.get('title')
                )
                
                if analysis:
                    return analysis
                else:
                    logger.warning(f"⚠️ Manual analysis returned no result for video {video_id}")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ Lyrics analysis failed after {max_retries} attempts for video {video_id}: {e}")
                else:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"⏳ Analysis attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
        
        return None
    
    async def _ai_lyrics_analysis(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        video_id: str,
        lyrics: str,
        song_title: Optional[str] = None
    ) -> Optional[LyricAnalysis]:
        """Use AI agent for intelligent lyrics analysis"""
        try:
            # Create analysis prompt
            prompt = f"""Analyze these song lyrics{f' from "{song_title}"' if song_title else ''}:

{lyrics[:2000]}  # Limit to avoid token overflow

Provide detailed analysis of themes, emotional content, sentiment, and lyrical style."""
            
            # Let the agent process and structure the analysis
            result = await self.agent.run(prompt, deps=deps)
            
            if result and hasattr(result, 'data'):
                analysis = result.data
                if isinstance(analysis, LyricAnalysis):
                    # Set required fields
                    analysis.artist_id = artist_id
                    analysis.video_id = video_id
                    analysis.language = "en"
                    analysis.analysis_metadata.update({
                        "analysis_method": "ai_powered",
                        "lyrics_length": len(lyrics),
                        "analyzed_at": datetime.now().isoformat()
                    })
                    return analysis
            
        except Exception as e:
            logger.error(f"AI lyrics analysis error: {e}")
        
        return None
    
    async def _manual_lyrics_analysis(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        video_id: str,
        lyrics: str,
        song_title: Optional[str] = None
    ) -> Optional[LyricAnalysis]:
        """Manual lyrics analysis as fallback"""
        try:
            # Extract key phrases and themes
            themes = self._extract_themes(lyrics)
            sentiment_score = self._calculate_sentiment(lyrics)
            emotional_content = self._extract_emotions(lyrics)
            lyrical_style = self._analyze_style(lyrics)
            
            analysis = LyricAnalysis(
                artist_id=artist_id,
                video_id=video_id,
                themes=themes,
                sentiment_score=sentiment_score,
                emotional_content=emotional_content,
                lyrical_style=lyrical_style,
                language="en",
                analysis_metadata={
                    "analysis_method": "manual_fallback",
                    "lyrics_length": len(lyrics),
                    "song_title": song_title,
                    "analyzed_at": datetime.now().isoformat()
                }
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Manual lyrics analysis error: {e}")
            return None
    
    async def _detect_language(self, text: str) -> str:
        """Detect the language of lyrics"""
        try:
            # Simple language detection based on common words
            # In production, use a proper language detection library
            
            english_words = set(['the', 'is', 'and', 'to', 'in', 'you', 'i', 'a', 'for', 'it', 'love', 'like', 'me', 'my'])
            spanish_words = set(['el', 'la', 'de', 'que', 'y', 'en', 'un', 'por', 'con', 'no', 'amor', 'mi', 'tu'])
            french_words = set(['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour'])
            
            words = text.lower().split()
            word_set = set(words)
            
            english_count = len(word_set.intersection(english_words))
            spanish_count = len(word_set.intersection(spanish_words))
            french_count = len(word_set.intersection(french_words))
            
            if spanish_count > english_count and spanish_count > french_count:
                return "es"
            elif french_count > english_count and french_count > spanish_count:
                return "fr"
            else:
                return "en"
                
        except:
            return "en"  # Default to English
    
    def _extract_themes(self, lyrics: str) -> List[str]:
        """Extract themes from lyrics using keyword analysis"""
        themes = []
        
        # Define theme keywords
        theme_keywords = {
            "love": ["love", "heart", "kiss", "romance", "together", "forever", "baby", "honey"],
            "heartbreak": ["broken", "cry", "tears", "goodbye", "miss", "alone", "hurt", "pain"],
            "success": ["money", "rich", "famous", "top", "win", "success", "achieve", "dream"],
            "party": ["party", "dance", "night", "club", "drink", "fun", "celebrate", "music"],
            "struggle": ["fight", "struggle", "hard", "tough", "difficult", "challenge", "overcome"],
            "friendship": ["friend", "together", "support", "loyalty", "trust", "team", "crew"],
            "family": ["family", "mother", "father", "home", "childhood", "roots", "heritage"],
            "spirituality": ["god", "pray", "faith", "believe", "soul", "heaven", "blessed"],
            "social_issues": ["justice", "change", "society", "problem", "world", "people", "community"]
        }
        
        lyrics_lower = lyrics.lower()
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in lyrics_lower for keyword in keywords):
                themes.append(theme)
        
        return themes[:5]  # Limit to top 5 themes
    
    def _calculate_sentiment(self, lyrics: str) -> float:
        """Calculate sentiment score from lyrics"""
        positive_words = set(["love", "happy", "joy", "beautiful", "amazing", "wonderful", "great", "good", "fun", "celebrate", "smile", "laugh"])
        negative_words = set(["hate", "sad", "cry", "pain", "hurt", "broken", "angry", "bad", "terrible", "awful", "wrong", "alone"])
        
        words = lyrics.lower().split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0
        
        # Normalize to -1 to 1 range
        sentiment = (positive_count - negative_count) / total_sentiment_words
        return max(-1.0, min(1.0, sentiment))
    
    def _extract_emotions(self, lyrics: str) -> List[str]:
        """Extract emotional content from lyrics"""
        emotions = []
        
        emotion_keywords = {
            "happy": ["happy", "joy", "smile", "laugh", "celebrate", "excited"],
            "sad": ["sad", "cry", "tears", "melancholy", "blue", "down"],
            "angry": ["angry", "mad", "rage", "furious", "pissed", "hate"],
            "confident": ["confident", "strong", "powerful", "boss", "king", "queen"],
            "nostalgic": ["remember", "memories", "past", "childhood", "yesterday", "miss"],
            "hopeful": ["hope", "future", "tomorrow", "dream", "believe", "faith"],
            "romantic": ["romantic", "love", "kiss", "heart", "beautiful", "gorgeous"]
        }
        
        lyrics_lower = lyrics.lower()
        
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in lyrics_lower for keyword in keywords):
                emotions.append(emotion)
        
        return emotions[:3]  # Limit to top 3 emotions
    
    def _analyze_style(self, lyrics: str) -> str:
        """Analyze lyrical style"""
        word_count = len(lyrics.split())
        unique_words = len(set(lyrics.lower().split()))
        
        # Calculate complexity metrics
        complexity_ratio = unique_words / word_count if word_count > 0 else 0
        
        # Simple style classification
        if complexity_ratio > 0.7:
            return "complex"
        elif complexity_ratio > 0.5:
            return "moderate"
        else:
            return "simple"
    
    async def generate_artist_summary(
        self,
        deps: PipelineDependencies,
        artist_name: str,
        analyses: List[LyricAnalysis]
    ) -> str:
        """Generate comprehensive artist summary from lyrics analyses"""
        
        if not analyses:
            return f"No lyrical analysis available for {artist_name}."
        
        # Aggregate themes
        all_themes = []
        for analysis in analyses:
            all_themes.extend(analysis.themes)
        
        theme_counts = Counter(all_themes)
        top_themes = [theme for theme, count in theme_counts.most_common(3)]
        
        # Calculate average sentiment
        avg_sentiment = sum(analysis.sentiment_score for analysis in analyses) / len(analyses)
        
        # Aggregate emotions
        all_emotions = []
        for analysis in analyses:
            all_emotions.extend(analysis.emotional_content)
        
        emotion_counts = Counter(all_emotions)
        top_emotions = [emotion for emotion, count in emotion_counts.most_common(2)]
        
        # Generate summary
        sentiment_desc = "positive" if avg_sentiment > 0.2 else "negative" if avg_sentiment < -0.2 else "neutral"
        
        summary = f"""
        {artist_name} demonstrates a {sentiment_desc} lyrical approach with an average sentiment score of {avg_sentiment:.2f}.
        
        Primary themes: {', '.join(top_themes) if top_themes else 'varied'}
        Emotional content: {', '.join(top_emotions) if top_emotions else 'mixed'}
        
        Analysis based on {len(analyses)} songs.
        """.strip()
        
        return summary

# Global instance for backward compatibility (but now properly initialized)
_lyrics_agent_instance = None

def get_lyrics_agent() -> LyricsAnalysisAgent:
    """Get global lyrics agent instance"""
    global _lyrics_agent_instance
    if _lyrics_agent_instance is None:
        _lyrics_agent_instance = LyricsAnalysisAgent()
    return _lyrics_agent_instance