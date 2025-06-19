#!/usr/bin/env python3
"""
Crawl4AI Diagnostics Script
Tests data extraction from various sources to identify parsing issues
"""

import asyncio
import json
import re
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from typing import Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlDiagnostics:
    def __init__(self):
        self.results = {}
    
    async def test_youtube_video(self, video_url: str = "https://www.youtube.com/watch?v=Tullamarine") -> Dict[str, Any]:
        """Test YouTube video page parsing"""
        logger.info(f"🔍 Testing YouTube video: {video_url}")
        
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=video_url,
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                # Extract key elements
                data = {
                    "url": video_url,
                    "title": self._extract_youtube_title(result.html),
                    "channel_name": self._extract_youtube_channel(result.html),
                    "channel_url": self._extract_youtube_channel_url(result.html),
                    "description": self._extract_youtube_description(result.html),
                    "view_count": self._extract_youtube_views(result.html),
                    "duration": self._extract_youtube_duration(result.html),
                    "html_length": len(result.html),
                    "markdown_length": len(result.markdown) if result.markdown else 0
                }
                
                # Look for social links in description
                if data["description"]:
                    data["social_links"] = self._extract_social_links(data["description"])
                
                logger.info(f"✅ YouTube extraction successful")
                logger.info(f"   Title: {data['title'][:100]}...")
                logger.info(f"   Channel: {data['channel_name']}")
                logger.info(f"   Views: {data['view_count']}")
                
                return data
            else:
                logger.error(f"❌ Failed to crawl YouTube: {result.error_message}")
                return {"error": result.error_message}
    
    async def test_spotify_artist(self, artist_url: str = "https://open.spotify.com/artist/4XD21vbRKQgevcDpWaDRw5") -> Dict[str, Any]:
        """Test Spotify artist page parsing"""
        logger.info(f"🔍 Testing Spotify artist: {artist_url}")
        
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=artist_url,
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                data = {
                    "url": artist_url,
                    "artist_name": self._extract_spotify_artist_name(result.html),
                    "monthly_listeners": self._extract_spotify_monthly_listeners(result.html),
                    "followers": self._extract_spotify_followers(result.html),
                    "biography": self._extract_spotify_bio(result.html),
                    "top_tracks": self._extract_spotify_tracks(result.html),
                    "genres": self._extract_spotify_genres(result.html),
                    "html_length": len(result.html),
                    "markdown_length": len(result.markdown) if result.markdown else 0
                }
                
                logger.info(f"✅ Spotify extraction successful")
                logger.info(f"   Artist: {data['artist_name']}")
                logger.info(f"   Monthly listeners: {data['monthly_listeners']}")
                logger.info(f"   Top tracks: {len(data['top_tracks'])} found")
                
                return data
            else:
                logger.error(f"❌ Failed to crawl Spotify: {result.error_message}")
                return {"error": result.error_message}
    
    async def test_musixmatch_lyrics(self, lyrics_url: str = "https://musixmatch.com/lyrics/the-tullamarines/lying") -> Dict[str, Any]:
        """Test Musixmatch lyrics page parsing"""
        logger.info(f"🔍 Testing Musixmatch lyrics: {lyrics_url}")
        
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=lyrics_url,
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                data = {
                    "url": lyrics_url,
                    "song_title": self._extract_musixmatch_title(result.html),
                    "artist_name": self._extract_musixmatch_artist(result.html),
                    "lyrics": self._extract_musixmatch_lyrics(result.html),
                    "html_length": len(result.html),
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "contains_lyrics_class": "lyrics__content__ok" in result.html,
                    "contains_mxm_track": "mxm-track" in result.html
                }
                
                logger.info(f"✅ Musixmatch extraction attempted")
                logger.info(f"   Song: {data['song_title']}")
                logger.info(f"   Artist: {data['artist_name']}")
                logger.info(f"   Lyrics found: {bool(data['lyrics'])}")
                
                return data
            else:
                logger.error(f"❌ Failed to crawl Musixmatch: {result.error_message}")
                return {"error": result.error_message}
    
    async def test_youtube_search(self, query: str = "indie rock official music video") -> Dict[str, Any]:
        """Test YouTube search results parsing"""
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=CAISCAgCEAEYAXAB&gl=US&hl=en"
        logger.info(f"🔍 Testing YouTube search: {search_url}")
        
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=search_url,
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                data = {
                    "url": search_url,
                    "videos_found": self._extract_youtube_search_videos(result.html),
                    "html_length": len(result.html),
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "video_containers": self._count_video_containers(result.html)
                }
                
                logger.info(f"✅ YouTube search extraction successful")
                logger.info(f"   Videos found: {len(data['videos_found'])}")
                logger.info(f"   Container counts: {data['video_containers']}")
                
                return data
            else:
                logger.error(f"❌ Failed to crawl YouTube search: {result.error_message}")
                return {"error": result.error_message}
    
    # Extraction methods
    def _extract_youtube_title(self, html: str) -> str:
        patterns = [
            r'<title>([^<]+)</title>',
            r'"title":"([^"]+)"',
            r'<meta name="title" content="([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).replace(" - YouTube", "")
        return ""
    
    def _extract_youtube_channel(self, html: str) -> str:
        patterns = [
            r'"ownerText":{"runs":\[{"text":"([^"]+)"',
            r'"channelName":"([^"]+)"',
            r'"author":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_youtube_channel_url(self, html: str) -> str:
        patterns = [
            r'"ownerNavigationEndpoint":{"clickTrackingParams":"[^"]+","commandMetadata":{"webCommandMetadata":{"url":"([^"]+)"',
            r'"channelUrl":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return "https://www.youtube.com" + match.group(1)
        return ""
    
    def _extract_youtube_description(self, html: str) -> str:
        patterns = [
            r'"shortDescription":"([^"]+)"',
            r'"description":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_youtube_views(self, html: str) -> str:
        patterns = [
            r'"viewCount":"([^"]+)"',
            r'"views":{"simpleText":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_youtube_duration(self, html: str) -> str:
        patterns = [
            r'"lengthText":"([^"]+)"',
            r'"duration":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_spotify_artist_name(self, html: str) -> str:
        patterns = [
            r'<title>([^|]+) \| Spotify</title>',
            r'"name":"([^"]+)".*"type":"artist"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_spotify_monthly_listeners(self, html: str) -> str:
        patterns = [
            r'(\d{1,3}(?:,\d{3})*) monthly listeners',
            r'"monthlyListeners":(\d+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_spotify_followers(self, html: str) -> str:
        patterns = [
            r'"followers":{"total":(\d+)',
            r'(\d{1,3}(?:,\d{3})*) followers'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_spotify_bio(self, html: str) -> str:
        patterns = [
            r'"biography":"([^"]+)"',
            r'<meta name="description" content="Listen to ([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""
    
    def _extract_spotify_tracks(self, html: str) -> List[str]:
        tracks = []
        patterns = [
            r'"name":"([^"]+)".*?"type":"track"',
            r'<div[^>]*data-testid="track-name"[^>]*>([^<]+)</div>'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html)
            tracks.extend(matches)
        return list(set(tracks))[:10]  # Top 10 unique
    
    def _extract_spotify_genres(self, html: str) -> List[str]:
        patterns = [
            r'"genres":\[([^\]]+)\]'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                genre_str = match.group(1)
                return [g.strip().strip('"') for g in genre_str.split(',')]
        return []
    
    def _extract_musixmatch_title(self, html: str) -> str:
        patterns = [
            r'<h1[^>]*class="[^"]*mxm-track-title[^"]*"[^>]*>([^<]+)</h1>',
            r'"track_name":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_musixmatch_artist(self, html: str) -> str:
        patterns = [
            r'<h2[^>]*class="[^"]*mxm-track-artist[^"]*"[^>]*>([^<]+)</h2>',
            r'"artist_name":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_musixmatch_lyrics(self, html: str) -> str:
        patterns = [
            r'<span[^>]*class="[^"]*lyrics__content__ok[^"]*"[^>]*>(.*?)</span>',
            r'"lyrics_body":"([^"]+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                lyrics = match.group(1)
                # Clean HTML tags
                lyrics = re.sub(r'<[^>]+>', '\n', lyrics)
                return lyrics.strip()
        return ""
    
    def _extract_social_links(self, text: str) -> Dict[str, str]:
        """Extract social media links from text"""
        links = {}
        patterns = {
            'spotify': r'(https?://(?:open\.)?spotify\.com/[^\s]+)',
            'instagram': r'(https?://(?:www\.)?instagram\.com/[^\s/]+)',
            'tiktok': r'(https?://(?:www\.)?tiktok\.com/@[^\s/]+)',
            'twitter': r'(https?://(?:www\.)?twitter\.com/[^\s/]+)',
            'facebook': r'(https?://(?:www\.)?facebook\.com/[^\s/]+)'
        }
        
        for platform, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                links[platform] = match.group(1)
        
        return links
    
    def _extract_youtube_search_videos(self, html: str) -> List[Dict[str, Any]]:
        """Extract video data from YouTube search results"""
        videos = []
        
        # Look for video data in JSON
        video_pattern = r'"videoRenderer":\s*({[^}]+})'
        matches = re.findall(video_pattern, html)
        
        for match in matches:
            try:
                video_data = json.loads(match)
                video = {
                    "title": video_data.get("title", {}).get("runs", [{}])[0].get("text", ""),
                    "video_id": video_data.get("videoId", ""),
                    "channel": video_data.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                    "views": video_data.get("viewCountText", {}).get("simpleText", ""),
                    "duration": video_data.get("lengthText", {}).get("simpleText", "")
                }
                if video["title"]:
                    videos.append(video)
            except json.JSONDecodeError:
                continue
        
        return videos
    
    def _count_video_containers(self, html: str) -> Dict[str, int]:
        """Count different types of video containers"""
        containers = {
            "ytd-video-renderer": len(re.findall(r'ytd-video-renderer', html)),
            "video-renderer": len(re.findall(r'class="[^"]*video-renderer[^"]*"', html)),
            "watch-urls": len(re.findall(r'href="[^"]*\/watch\?v=', html)),
            "video-titles": len(re.findall(r'"title":\s*{"runs"', html))
        }
        return containers

    async def run_all_tests(self):
        """Run all diagnostic tests"""
        logger.info("🚀 Starting Crawl4AI diagnostics...")
        
        # Test 1: YouTube video
        self.results["youtube_video"] = await self.test_youtube_video()
        
        # Test 2: Spotify artist
        self.results["spotify_artist"] = await self.test_spotify_artist()
        
        # Test 3: Musixmatch lyrics
        self.results["musixmatch_lyrics"] = await self.test_musixmatch_lyrics()
        
        # Test 4: YouTube search
        self.results["youtube_search"] = await self.test_youtube_search()
        
        return self.results

    def save_results(self, filename: str = "crawl4ai_diagnostics.json"):
        """Save diagnostic results to file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"💾 Results saved to {filename}")

async def main():
    diagnostics = CrawlDiagnostics()
    results = await diagnostics.run_all_tests()
    diagnostics.save_results()
    
    # Print summary
    print("\n" + "="*80)
    print("🔍 CRAWL4AI DIAGNOSTICS SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        print(f"\n📊 {test_name.upper()}:")
        if "error" in result:
            print(f"   ❌ ERROR: {result['error']}")
        else:
            print(f"   ✅ SUCCESS")
            print(f"   📏 HTML: {result.get('html_length', 0):,} chars")
            print(f"   📝 Markdown: {result.get('markdown_length', 0):,} chars")
            
            # Specific data points
            if test_name == "youtube_video":
                print(f"   🎬 Title: {result.get('title', 'Not found')[:50]}...")
                print(f"   📺 Channel: {result.get('channel_name', 'Not found')}")
                print(f"   👀 Views: {result.get('view_count', 'Not found')}")
                print(f"   🔗 Social links: {len(result.get('social_links', {}))}")
            
            elif test_name == "spotify_artist":
                print(f"   🎤 Artist: {result.get('artist_name', 'Not found')}")
                print(f"   👥 Monthly listeners: {result.get('monthly_listeners', 'Not found')}")
                print(f"   🎵 Tracks found: {len(result.get('top_tracks', []))}")
            
            elif test_name == "musixmatch_lyrics":
                print(f"   🎵 Song: {result.get('song_title', 'Not found')}")
                print(f"   🎤 Artist: {result.get('artist_name', 'Not found')}")
                print(f"   📝 Lyrics: {bool(result.get('lyrics'))}")
            
            elif test_name == "youtube_search":
                print(f"   🎬 Videos found: {len(result.get('videos_found', []))}")
                containers = result.get('video_containers', {})
                for container_type, count in containers.items():
                    print(f"   📦 {container_type}: {count}")

if __name__ == "__main__":
    asyncio.run(main())