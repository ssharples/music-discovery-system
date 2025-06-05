# backend/app/agents/lyrics_agent.py
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import List, Dict, Any, Optional
import logging
import re
from collections import Counter
import json

from app.core.dependencies import PipelineDependencies
from app.models.artist import LyricAnalysis, VideoMetadata

logger = logging.getLogger(__name__)

# Create Lyrics Analysis Agent
lyrics_agent = Agent(
    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
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
    
    Provide concise, insightful analysis suitable for music industry professionals.
    """
)

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

@lyrics_agent.tool
async def analyze_lyrics_content(
    ctx: RunContext[PipelineDependencies],
    lyrics: str,
    song_title: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze lyrics content using GPT"""
    try:
        # Clean and prepare lyrics
        cleaned_lyrics = clean_lyrics(lyrics)
        
        if len(cleaned_lyrics) < 50:
            return {
                "error": "Insufficient lyrics content",
                "themes": [],
                "sentiment_score": 0.0
            }
        
        # Create analysis prompt
        prompt = f"""Analyze these song lyrics{f' from "{song_title}"' if song_title else ''}:

[Lyrics content provided for analysis]

Provide a detailed analysis including:
1. Main themes and topics (list top 3-5)
2. Emotional content and mood
3. Lyrical style (simple/complex, narrative/abstract, etc.)
4. Subject matter and overall message
5. Target audience

Return as JSON with keys: themes, emotional_content, lyrical_style, subject_matter, sentiment_score (-1 to 1)"""

        # Use DeepSeek to analyze
        response = await ctx.deps.http_client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {ctx.deps.deepseek_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": lyrics_agent.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            analysis = json.loads(result["choices"][0]["message"]["content"])
            return analysis
        else:
            logger.error(f"DeepSeek API error: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"Lyrics analysis error: {e}")
        return {}

@lyrics_agent.tool
async def extract_key_phrases(
    ctx: RunContext[PipelineDependencies],
    lyrics: str
) -> List[str]:
    """Extract key phrases and hooks from lyrics"""
    try:
        cleaned = clean_lyrics(lyrics)
        
        # Split into lines
        lines = [l.strip() for l in cleaned.split('.') if l.strip()]
        
        # Find repeated phrases (potential hooks/chorus)
        phrase_counts = Counter()
        for line in lines:
            if len(line) > 10:  # Meaningful phrases only
                phrase_counts[line] += 1
        
        # Get most common phrases
        key_phrases = [phrase for phrase, count in phrase_counts.most_common(5) if count > 1]
        
        return key_phrases
        
    except Exception as e:
        logger.error(f"Key phrase extraction error: {e}")
        return []

@lyrics_agent.tool
async def detect_language(
    ctx: RunContext[PipelineDependencies],
    text: str
) -> str:
    """Detect the language of lyrics"""
    try:
        # Simple language detection based on common words
        # In production, use a proper language detection library
        
        english_words = set(['the', 'is', 'and', 'to', 'in', 'you', 'i', 'a', 'for', 'it'])
        spanish_words = set(['el', 'la', 'de', 'que', 'y', 'en', 'un', 'por', 'con', 'no'])
        
        words = text.lower().split()
        word_set = set(words)
        
        english_count = len(word_set.intersection(english_words))
        spanish_count = len(word_set.intersection(spanish_words))
        
        if spanish_count > english_count:
            return "es"
        else:
            return "en"
            
    except:
        return "en"  # Default to English

class LyricsAnalysisAgent:
    """Lyrics analysis agent wrapper"""
    
    def __init__(self):
        self.agent = lyrics_agent
        
    async def analyze_artist_lyrics(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        videos_with_captions: List[Dict[str, Any]]
    ) -> List[LyricAnalysis]:
        """Analyze lyrics from multiple videos"""
        
        analyses = []
        
        for video in videos_with_captions:
            if not video.get('captions'):
                continue
                
            # Detect language
            language = await detect_language(
                RunContext(deps=deps, retry=0, tool_name="detect_language"),
                text=video['captions']
            )
            
            # Only analyze English content for now
            if language != 'en':
                continue
            
            # Analyze lyrics
            analysis_result = await analyze_lyrics_content(
                RunContext(deps=deps, retry=0, tool_name="analyze_lyrics_content"),
                lyrics=video['captions'],
                song_title=video.get('title')
            )
            
            if analysis_result and not analysis_result.get('error'):
                # Extract key phrases
                key_phrases = await extract_key_phrases(
                    RunContext(deps=deps, retry=0, tool_name="extract_key_phrases"),
                    lyrics=video['captions']
                )
                
                # Create analysis object
                analysis = LyricAnalysis(
                    video_id=video['video_id'],
                    artist_id=artist_id,
                    themes=analysis_result.get('themes', []),
                    sentiment_score=analysis_result.get('sentiment_score', 0.0),
                    emotional_content=analysis_result.get('emotional_content', []),
                    lyrical_style=analysis_result.get('lyrical_style', ''),
                    subject_matter=analysis_result.get('subject_matter', ''),
                    language=language,
                    analysis_metadata={
                        'key_phrases': key_phrases,
                        'word_count': len(video['captions'].split()),
                        'video_title': video.get('title', '')
                    }
                )
                
                analyses.append(analysis)
                
        return analyses
        
    async def generate_artist_summary(
        self,
        deps: PipelineDependencies,
        artist_name: str,
        analyses: List[LyricAnalysis]
    ) -> str:
        """Generate a summary of what the artist typically sings about"""
        
        if not analyses:
            return "No lyrical analysis available for this artist."
            
        # Aggregate themes and emotional content
        all_themes = []
        all_emotions = []
        sentiment_scores = []
        
        for analysis in analyses:
            all_themes.extend(analysis.themes)
            all_emotions.extend(analysis.emotional_content)
            sentiment_scores.append(analysis.sentiment_score)
            
        # Count occurrences
        theme_counts = Counter(all_themes)
        emotion_counts = Counter(all_emotions)
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        # Get most common elements
        top_themes = [theme for theme, _ in theme_counts.most_common(3)]
        top_emotions = [emotion for emotion, _ in emotion_counts.most_common(3)]
        
        # Generate summary using DeepSeek
        prompt = f"""Create a 2-3 sentence professional summary of what music artist '{artist_name}' typically expresses in their music.

Based on analysis of their songs:
- Main themes: {', '.join(top_themes)}
- Emotional content: {', '.join(top_emotions)}
- Overall sentiment: {'Positive' if avg_sentiment > 0.2 else 'Negative' if avg_sentiment < -0.2 else 'Mixed'}
- Number of songs analyzed: {len(analyses)}

Write a concise summary focusing on their artistic expression and themes."""

        try:
            response = await deps.http_client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {deps.deepseek_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a music industry analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 150
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            
        # Fallback summary
        return f"{artist_name} explores themes of {', '.join(top_themes[:2])} with {top_emotions[0]} undertones in their music."