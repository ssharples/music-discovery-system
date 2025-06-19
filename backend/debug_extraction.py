#!/usr/bin/env python3
"""
Debug Extraction Script
Analyzes raw HTML content to understand why data extraction is failing
"""

import asyncio
import json
import re
from crawl4ai import AsyncWebCrawler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_youtube_video():
    """Debug YouTube video page to see what data is actually available"""
    url = "https://www.youtube.com/watch?v=Tullamarine"
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            bypass_cache=True
        )
        
        if result.success:
            html = result.html
            
            print("="*80)
            print("🔍 YOUTUBE VIDEO DEBUG")
            print("="*80)
            print(f"HTML Length: {len(html):,} chars")
            print(f"Markdown Length: {len(result.markdown):,} chars")
            
            # Check if page loaded properly
            print(f"\n📊 PAGE STRUCTURE:")
            print(f"   Contains 'ytInitialData': {'ytInitialData' in html}")
            print(f"   Contains 'ytInitialPlayerResponse': {'ytInitialPlayerResponse' in html}")
            print(f"   Contains 'videoDetails': {'videoDetails' in html}")
            print(f"   Contains 'videoOwnerRenderer': {'videoOwnerRenderer' in html}")
            
            # Extract title patterns
            print(f"\n🎬 TITLE EXTRACTION:")
            title_patterns = [
                (r'<title>([^<]+)</title>', "HTML title tag"),
                (r'"title":"([^"]+)"', "JSON title field"),
                (r'"videoDetails":[^}]*"title":"([^"]+)"', "videoDetails title"),
                (r'<meta property="og:title" content="([^"]*)"', "OG title")
            ]
            
            for pattern, desc in title_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:3] if matches else 'None'}")
            
            # Extract channel patterns
            print(f"\n📺 CHANNEL EXTRACTION:")
            channel_patterns = [
                (r'"ownerText":{"runs":\[{"text":"([^"]+)"', "ownerText runs"),
                (r'"videoOwnerRenderer":[^}]*"title":{"runs":\[{"text":"([^"]+)"', "videoOwnerRenderer title"),
                (r'"channelName":"([^"]+)"', "channelName field"),
                (r'"author":"([^"]+)"', "author field")
            ]
            
            for pattern, desc in channel_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:3] if matches else 'None'}")
            
            # Look for actual content in markdown
            print(f"\n📝 MARKDOWN CONTENT:")
            if result.markdown:
                lines = result.markdown.split('\n')[:20]
                for i, line in enumerate(lines, 1):
                    if line.strip():
                        print(f"   {i:2}: {line[:80]}...")
            
            # Check for JavaScript data
            print(f"\n🔧 JAVASCRIPT DATA:")
            js_patterns = [
                (r'var ytInitialData = ({.*?});', "ytInitialData"),
                (r'var ytInitialPlayerResponse = ({.*?});', "ytInitialPlayerResponse")
            ]
            
            for pattern, desc in js_patterns:
                match = re.search(pattern, html)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        print(f"   {desc}: Found valid JSON ({len(str(data)):,} chars)")
                        
                        # Extract from ytInitialData
                        if desc == "ytInitialData" and "contents" in data:
                            try:
                                # Navigate through the structure
                                video_primary = data.get("contents", {}).get("twoColumnWatchNextResults", {}).get("results", {}).get("results", {}).get("contents", [])
                                for content in video_primary:
                                    if "videoPrimaryInfoRenderer" in content:
                                        title_info = content["videoPrimaryInfoRenderer"].get("title", {})
                                        if "runs" in title_info:
                                            actual_title = title_info["runs"][0].get("text", "")
                                            print(f"   🎬 ACTUAL TITLE: {actual_title}")
                                        
                                        # Look for view count
                                        view_info = content["videoPrimaryInfoRenderer"].get("viewCount", {})
                                        if "videoViewCountRenderer" in view_info:
                                            view_text = view_info["videoViewCountRenderer"].get("viewCount", {}).get("simpleText", "")
                                            print(f"   👀 ACTUAL VIEWS: {view_text}")
                                    
                                    elif "videoSecondaryInfoRenderer" in content:
                                        owner_info = content["videoSecondaryInfoRenderer"].get("owner", {}).get("videoOwnerRenderer", {})
                                        if "title" in owner_info and "runs" in owner_info["title"]:
                                            channel_name = owner_info["title"]["runs"][0].get("text", "")
                                            print(f"   📺 ACTUAL CHANNEL: {channel_name}")
                                        
                                        # Get channel URL
                                        nav_endpoint = owner_info.get("title", {}).get("runs", [{}])[0].get("navigationEndpoint", {})
                                        if "commandMetadata" in nav_endpoint:
                                            channel_url = nav_endpoint["commandMetadata"].get("webCommandMetadata", {}).get("url", "")
                                            print(f"   🔗 CHANNEL URL: https://www.youtube.com{channel_url}")
                            except Exception as e:
                                print(f"   ❌ Error parsing ytInitialData: {e}")
                        
                    except json.JSONDecodeError as e:
                        print(f"   {desc}: Invalid JSON - {e}")
                else:
                    print(f"   {desc}: Not found")

async def debug_spotify_artist():
    """Debug Spotify artist page"""
    url = "https://open.spotify.com/artist/4XD21vbRKQgevcDpWaDRw5"
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            bypass_cache=True
        )
        
        if result.success:
            html = result.html
            
            print("="*80)
            print("🔍 SPOTIFY ARTIST DEBUG")
            print("="*80)
            print(f"HTML Length: {len(html):,} chars")
            
            # Check page structure
            print(f"\n📊 PAGE STRUCTURE:")
            print(f"   Contains 'pageData': {'pageData' in html}")
            print(f"   Contains 'monthly listeners': {'monthly listeners' in html}")
            print(f"   Contains 'followers': {'followers' in html}")
            artist_data_check = '"type":"artist"' in html
            print(f"   Contains artist data: {artist_data_check}")
            
            # Look for monthly listeners patterns
            print(f"\n👥 MONTHLY LISTENERS:")
            listener_patterns = [
                (r'(\d{1,3}(?:,\d{3})*) monthly listeners', "Text pattern"),
                (r'"monthlyListeners":(\d+)', "JSON field"),
                (r'(\d{1,3}(?:\.\d+)?K) monthly listeners', "K format"),
                (r'"stats":[^}]*"monthlyListeners":(\d+)', "Stats object")
            ]
            
            for pattern, desc in listener_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:3] if matches else 'None'}")
            
            # Look for track patterns
            print(f"\n🎵 TRACKS:")
            track_patterns = [
                (r'"name":"([^"]+)"[^}]*"type":"track"', "Track objects"),
                (r'data-testid="track-name"[^>]*>([^<]+)', "Track name elements"),
                (r'"title":"([^"]+)"[^}]*"uri":"spotify:track:', "Track URIs")
            ]
            
            for pattern, desc in track_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:5] if matches else 'None'}")
            
            # Check markdown content
            print(f"\n📝 MARKDOWN CONTENT:")
            if result.markdown:
                lines = result.markdown.split('\n')
                for line in lines[:10]:
                    if line.strip() and not line.startswith('#'):
                        print(f"   {line[:80]}...")

async def debug_musixmatch():
    """Debug Musixmatch lyrics page"""
    url = "https://musixmatch.com/lyrics/the-tullamarines/lying"
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            bypass_cache=True
        )
        
        if result.success:
            html = result.html
            
            print("="*80)
            print("🔍 MUSIXMATCH LYRICS DEBUG")
            print("="*80)
            print(f"HTML Length: {len(html):,} chars")
            
            # Check page structure
            print(f"\n📊 PAGE STRUCTURE:")
            print(f"   Contains 'lyrics': {'lyrics' in html}")
            print(f"   Contains 'mxm-track': {'mxm-track' in html}")
            print(f"   Contains 'track-name': {'track-name' in html}")
            print(f"   Contains lyrics class: {'lyrics__content__ok' in html}")
            
            # Look for title patterns
            print(f"\n🎵 SONG TITLE:")
            title_patterns = [
                (r'<h1[^>]*class="[^"]*mxm-track-title[^"]*"[^>]*>([^<]+)</h1>', "H1 track title"),
                (r'"track_name":"([^"]+)"', "JSON track name"),
                (r'<title>([^|]+) \| Musixmatch</title>', "Page title"),
                (r'data-reactid="[^"]*"[^>]*>([^<]+)</[^>]*>[^<]*Lyrics', "Title before Lyrics")
            ]
            
            for pattern, desc in title_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:3] if matches else 'None'}")
            
            # Look for artist patterns
            print(f"\n🎤 ARTIST NAME:")
            artist_patterns = [
                (r'<h2[^>]*class="[^"]*mxm-track-artist[^"]*"[^>]*>([^<]+)</h2>', "H2 artist"),
                (r'"artist_name":"([^"]+)"', "JSON artist name"),
                (r'<a[^>]*href="/artist/[^"]*"[^>]*>([^<]+)</a>', "Artist link")
            ]
            
            for pattern, desc in artist_patterns:
                matches = re.findall(pattern, html)
                print(f"   {desc}: {matches[:3] if matches else 'None'}")
            
            # Look for lyrics patterns
            print(f"\n📝 LYRICS:")
            lyrics_patterns = [
                (r'<span[^>]*class="[^"]*lyrics__content__ok[^"]*"[^>]*>(.*?)</span>', "Lyrics span"),
                (r'"lyrics_body":"([^"]+)"', "JSON lyrics body"),
                (r'class="mxm-lyrics__content"[^>]*>(.*?)</div>', "Lyrics content div")
            ]
            
            for pattern, desc in lyrics_patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    content = matches[0][:200] + "..." if len(matches[0]) > 200 else matches[0]
                    print(f"   {desc}: Found content ({len(matches[0])} chars)")
                    print(f"      Preview: {content}")
                else:
                    print(f"   {desc}: None")

async def main():
    print("🚀 Starting detailed extraction debugging...")
    
    await debug_youtube_video()
    await debug_spotify_artist()
    await debug_musixmatch()
    
    print("\n" + "="*80)
    print("🎯 DEBUGGING COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())