#!/usr/bin/env python3
"""
Test Enhanced Extractors
Verify that the fixed extraction methods work with real data
"""

import asyncio
import logging
from enhanced_extractors import EnhancedYouTubeExtractor, EnhancedSpotifyExtractor, EnhancedMusixmatchExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_extractors():
    """Test all enhanced extractors with real URLs"""
    
    print("🚀 Testing Enhanced Extractors with Real Data")
    print("=" * 60)
    
    # Test URLs with real, popular artists
    test_urls = {
        "youtube_search": "https://www.youtube.com/results?search_query=official+music+video+2024&sp=CAISCAgCEAEYAXAB&gl=US&hl=en",
        "youtube_video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
        "spotify_artist": "https://open.spotify.com/artist/1dfeR4HaWDbWqFHLkxsg1d",  # Queen
        "musixmatch_lyrics": "https://musixmatch.com/lyrics/Queen/Bohemian-Rhapsody"
    }
    
    from crawl4ai import AsyncWebCrawler
    
    # Test 1: YouTube Search
    print("\n📺 Testing YouTube Search Extraction...")
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=test_urls["youtube_search"],
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                videos = EnhancedYouTubeExtractor.extract_search_videos(result.html, max_results=5)
                print(f"✅ YouTube Search: Found {len(videos)} videos")
                for i, video in enumerate(videos[:3], 1):
                    print(f"   {i}. {video.get('title', 'No title')[:50]}...")
                    print(f"      Channel: {video.get('channel_name', 'Unknown')}")
                    print(f"      Views: {video.get('view_count', 'Unknown')}")
            else:
                print(f"❌ YouTube Search failed: {result.error_message}")
    except Exception as e:
        print(f"❌ YouTube Search error: {e}")
    
    # Test 2: YouTube Video
    print("\n🎬 Testing YouTube Video Extraction...")
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=test_urls["youtube_video"],
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                video_data = EnhancedYouTubeExtractor.extract_video_data(result.html)
                print(f"✅ YouTube Video:")
                print(f"   Title: {video_data.get('title', 'Not found')}")
                print(f"   Channel: {video_data.get('channel_name', 'Not found')}")
                print(f"   Views: {video_data.get('view_count', 'Not found')}")
                print(f"   Description: {video_data.get('description', 'Not found')[:100]}...")
            else:
                print(f"❌ YouTube Video failed: {result.error_message}")
    except Exception as e:
        print(f"❌ YouTube Video error: {e}")
    
    # Test 3: Spotify Artist
    print("\n🎵 Testing Spotify Artist Extraction...")
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=test_urls["spotify_artist"],
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                artist_data = EnhancedSpotifyExtractor.extract_artist_data(result.html)
                print(f"✅ Spotify Artist:")
                print(f"   Artist: {artist_data.get('artist_name', 'Not found')}")
                print(f"   Monthly Listeners: {artist_data.get('monthly_listeners', 'Not found')}")
                print(f"   Followers: {artist_data.get('followers', 'Not found')}")
                print(f"   Top Tracks: {len(artist_data.get('top_tracks', []))} found")
                print(f"   Genres: {artist_data.get('genres', [])}")
                print(f"   Biography: {artist_data.get('biography', 'Not found')[:100]}...")
            else:
                print(f"❌ Spotify Artist failed: {result.error_message}")
    except Exception as e:
        print(f"❌ Spotify Artist error: {e}")
    
    # Test 4: Musixmatch Lyrics
    print("\n🎤 Testing Musixmatch Lyrics Extraction...")
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=test_urls["musixmatch_lyrics"],
                word_count_threshold=1,
                bypass_cache=True
            )
            
            if result.success:
                lyrics_data = EnhancedMusixmatchExtractor.extract_lyrics_data(result.html)
                print(f"✅ Musixmatch Lyrics:")
                print(f"   Song: {lyrics_data.get('song_title', 'Not found')}")
                print(f"   Artist: {lyrics_data.get('artist_name', 'Not found')}")
                lyrics = lyrics_data.get('lyrics', '')
                if lyrics:
                    print(f"   Lyrics: Found {len(lyrics)} characters")
                    print(f"   Preview: {lyrics[:100]}...")
                else:
                    print(f"   Lyrics: Not found")
            else:
                print(f"❌ Musixmatch Lyrics failed: {result.error_message}")
    except Exception as e:
        print(f"❌ Musixmatch Lyrics error: {e}")
    
    print("\n🎯 Enhanced Extractor Testing Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_enhanced_extractors())