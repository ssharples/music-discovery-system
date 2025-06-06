#!/usr/bin/env python3
"""
Test script to verify artist name extraction from video titles
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.agents.youtube_agent import YouTubeDiscoveryAgent

def test_artist_name_extraction():
    """Test artist name extraction with various video title formats"""
    
    agent = YouTubeDiscoveryAgent()
    
    # Test cases with various video title formats
    test_cases = [
        {
            "channel_title": "SomeRandomChannelName123",
            "qualifying_videos": [
                {"title": "John Smith - Beautiful Song (Official Music Video)"},
                {"title": "John Smith - Another Track"},
                {"title": "John Smith | Live Performance"}
            ],
            "expected": "John Smith"
        },
        {
            "channel_title": "MusicChannelXYZ",
            "qualifying_videos": [
                {"title": "Sarah Williams: New Single 2024"},
                {"title": "Sarah Williams: Dance Tonight"},
                {"title": "Sarah Williams: Memories (Audio)"}
            ],
            "expected": "Sarah Williams"
        },
        {
            "channel_title": "OfficialArtistVEVO",
            "qualifying_videos": [
                {"title": "Amazing Song by Michael Johnson"},
                {"title": "Love Story by Michael Johnson (Official Video)"},
                {"title": "Michael Johnson performs live"}
            ],
            "expected": "Michael Johnson"
        },
        {
            "channel_title": "RandomMusic Records",
            "qualifying_videos": [
                {"title": "Emma Davis - Sunrise (Official Audio)"},
                {"title": "Emma Davis - Dancing Queen"},
                {"title": "Emma Davis - Summer Vibes (Lyric Video)"}
            ],
            "expected": "Emma Davis"
        },
        {
            "channel_title": "TheOfficialArtist",
            "qualifying_videos": [
                {"title": "Official Music Video 2024"},
                {"title": "New Song Audio"},
                {"title": "Latest Track"}
            ],
            "expected": None  # Should fall back to channel title since no clear artist name
        }
    ]
    
    print("🧪 Testing Artist Name Extraction")
    print("=" * 50)
    
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        channel_data = {
            "channel_title": test_case["channel_title"],
            "qualifying_videos": test_case["qualifying_videos"]
        }
        
        extracted = agent._extract_artist_name_from_videos(channel_data)
        expected = test_case["expected"]
        
        print(f"\nTest {i}: {test_case['channel_title']}")
        print(f"  Video titles:")
        for video in test_case["qualifying_videos"]:
            print(f"    - {video['title']}")
        print(f"  Expected: {expected}")
        print(f"  Extracted: {extracted}")
        
        if extracted == expected:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Artist name extraction is working correctly.")
    else:
        print("⚠️  Some tests failed. Review the extraction logic.")
    
    return passed == total

def test_validation_functions():
    """Test the validation helper functions"""
    
    agent = YouTubeDiscoveryAgent()
    
    print("\n🔍 Testing Validation Functions")
    print("=" * 50)
    
    # Test _is_likely_not_artist_name
    not_artist_names = [
        "Official", "Music Video", "2024", "Official Music Video", 
        "feat", "remix", "", "a", "YouTube", "VEVO Records"
    ]
    
    artist_names = [
        "John Smith", "Sarah Williams", "The Beatles", "Ariana Grande",
        "Taylor Swift", "Ed Sheeran", "Dua Lipa"
    ]
    
    print("\nTesting _is_likely_not_artist_name:")
    for name in not_artist_names:
        result = agent._is_likely_not_artist_name(name)
        print(f"  '{name}' -> {result} ({'✅' if result else '❌'})")
    
    print("\nTesting artist names (should return False):")
    for name in artist_names:
        result = agent._is_likely_not_artist_name(name)
        print(f"  '{name}' -> {result} ({'❌' if result else '✅'})")
    
    print("\nTesting _validate_artist_name:")
    for name in artist_names:
        result = agent._validate_artist_name(name)
        print(f"  '{name}' -> {result} ({'✅' if result else '❌'})")

if __name__ == "__main__":
    success = test_artist_name_extraction()
    test_validation_functions()
    
    if success:
        print("\n🎯 Artist name extraction is ready for production!")
    else:
        print("\n🔧 Artist name extraction needs refinement.") 