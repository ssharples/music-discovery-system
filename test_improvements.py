#!/usr/bin/env python3
"""
Test script for the improved music discovery system.
Tests all the new filtering and validation features.
"""

import sys
sys.path.append('/Users/satti/Desktop/music-discovery-system/backend')

from app.agents.master_discovery_agent import MasterDiscoveryAgent

def test_validation_functions():
    """Test all the new validation functions."""
    agent = MasterDiscoveryAgent()
    
    print("🔍 Testing Master Discovery Agent Improvements")
    print("=" * 60)
    
    # Test 1: View count filtering
    print("\n1. Testing View Count Filtering:")
    test_cases = [
        (45000, True, "Below 50k limit"),
        (50000, False, "At 50k limit"),
        (75000, False, "Above 50k limit"),
        ("45K", True, "String format 45K"),
        ("1.2M", False, "String format 1.2M"),
        (None, True, "None value"),
    ]
    
    for view_count, expected, description in test_cases:
        result = agent._validate_view_count(view_count)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {description}: {view_count} -> {result}")
    
    # Test 2: English language validation
    print("\n2. Testing English Language Validation:")
    test_cases = [
        ("John Doe", True, "Simple English name"),
        ("MC Hammer", True, "English with space"),
        ("Twenty-One Pilots", True, "English with hyphen"),
        ("José María", False, "Spanish with accents"),
        ("李小龙", False, "Chinese characters"),
        ("Тест", False, "Cyrillic characters"),
        ("", False, "Empty string"),
    ]
    
    for text, expected, description in test_cases:
        result = agent._validate_english_language(text)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {description}: '{text}' -> {result}")
    
    # Test 3: Well-known artist detection
    print("\n3. Testing Well-Known Artist Detection:")
    test_cases = [
        ("Taylor Swift", True, "Exact match"),
        ("taylor swift", True, "Case insensitive"),
        ("Drake", True, "Single name match"),
        ("Unknown Artist", False, "Unknown artist"),
        ("Taylor Swift Cover", True, "Contains well-known name"),
        ("John Smith", False, "Generic name"),
    ]
    
    for artist_name, expected, description in test_cases:
        result = agent._is_well_known_artist(artist_name)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {description}: '{artist_name}' -> {result}")
    
    # Test 4: Enhanced content validation
    print("\n4. Testing Enhanced Content Validation:")
    test_cases = [
        ("John Doe - Amazing Song", "", True, "Clean title and description"),
        ("AI Generated Music", "", False, "Contains 'AI'"),
        ("Song Title", "Created with Suno AI", False, "Contains 'suno' in description"),
        ("Cover Song", "", False, "Contains 'cover'"),
        ("Remix Version", "", False, "Contains 'remix'"),
        ("Remastered Edition", "", False, "Contains 'remastered'"),
        ("Original Song", "Official music video", True, "Clean content"),
    ]
    
    for title, description, expected, test_description in test_cases:
        result = agent._validate_content(title, description)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {test_description}: '{title}' + '{description}' -> {result}")
    
    # Test 5: Simple lyrics analysis
    print("\n5. Testing Simple Lyrics Analysis:")
    test_lyrics = {
        "Love Song": "I love you baby, my heart belongs to you, together forever",
        "Money Song": "Making money, cash flow, success and riches, gold chains",
        "Party Song": "Party all night, dance floor, club lights, celebrate good times"
    }
    
    for song, lyrics in test_lyrics.items():
        analysis = agent._simple_lyrics_analysis(lyrics)
        print(f"   📝 {song}: '{analysis}'")
    
    print("\n" + "=" * 60)
    print("🎉 All validation tests completed!")
    print("\n🔧 Configured Settings:")
    print(f"   • Max view count: {agent.max_view_count:,}")
    print(f"   • Exclude keywords: {len(agent.exclude_keywords)} keywords")
    print(f"   • Well-known artists: {len(agent.well_known_artists)} artists")
    
    return True

if __name__ == "__main__":
    test_validation_functions()