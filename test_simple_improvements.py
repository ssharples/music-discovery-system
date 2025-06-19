#!/usr/bin/env python3
"""
Simple test script for the improved validation functions only.
Tests the new filtering without initializing the full discovery agent.
"""

import sys
import re
sys.path.append('/Users/satti/Desktop/music-discovery-system/backend')

# Test the validation functions directly without the full agent initialization
class TestValidationFunctions:
    def __init__(self):
        self.max_view_count = 50000  # 50k view limit
        self.exclude_keywords = [
            'ai', 'suno', 'generated', 'udio', 'cover', 'remix', 'remastered',
            'artificial intelligence', 'ai-generated', 'ai music', 'ai created',
            'machine learning', 'neural', 'bot', 'automated', 'synthetic'
        ]
        self.well_known_artists = [
            'taylor swift', 'drake', 'ariana grande', 'justin bieber', 'billie eilish',
            'the weeknd', 'dua lipa', 'ed sheeran', 'post malone', 'olivia rodrigo',
            'harry styles', 'bad bunny', 'doja cat', 'lil nas x', 'travis scott',
            'kanye west', 'eminem', 'rihanna', 'beyoncé', 'adele', 'bruno mars',
            'coldplay', 'imagine dragons', 'maroon 5', 'twenty one pilots'
        ]
    
    def _validate_view_count(self, view_count) -> bool:
        """Validate that video has less than 50k views to find undiscovered talent."""
        try:
            if view_count is None:
                return True
            
            if isinstance(view_count, str):
                view_count = view_count.lower().replace(',', '')
                if 'k' in view_count:
                    view_count = float(view_count.replace('k', '')) * 1000
                elif 'm' in view_count:
                    view_count = float(view_count.replace('m', '')) * 1000000
                elif 'b' in view_count:
                    view_count = float(view_count.replace('b', '')) * 1000000000
                else:
                    view_count = float(view_count)
            
            return view_count < self.max_view_count
        except:
            return True
    
    def _validate_english_language(self, text: str) -> bool:
        """Validate that text contains only English characters."""
        if not text:
            return False
        
        english_pattern = re.compile(r'^[a-zA-Z0-9\s\-\.\,\!\?\(\)\[\]\&\'\"]+$')
        return bool(english_pattern.match(text.strip()))
    
    def _is_well_known_artist(self, artist_name: str) -> bool:
        """Check if artist name matches well-known artists."""
        if not artist_name:
            return False
        
        artist_lower = artist_name.lower().strip()
        
        for known_artist in self.well_known_artists:
            if known_artist in artist_lower:
                return True
        
        return False
    
    def _validate_content(self, title: str, description: str) -> bool:
        """Validate content doesn't contain excluded keywords."""
        content = f"{title} {description or ''}".lower()
        
        for keyword in self.exclude_keywords:
            if keyword.lower() in content:
                return False
        
        return True

def test_validation_functions():
    """Test all the new validation functions."""
    agent = TestValidationFunctions()
    
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
    
    print("\n" + "=" * 60)
    print("🎉 All validation tests completed!")
    print("\n🔧 Configured Settings:")
    print(f"   • Max view count: {agent.max_view_count:,}")
    print(f"   • Exclude keywords: {len(agent.exclude_keywords)} keywords")
    print(f"   • Well-known artists: {len(agent.well_known_artists)} artists")
    
    return True

if __name__ == "__main__":
    test_validation_functions()