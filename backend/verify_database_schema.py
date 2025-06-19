#!/usr/bin/env python3
"""
Verify that the artists table has all required fields for the discovery system.
Run this after executing update_artists_table.sql
"""

import asyncio
from app.core.dependencies import get_supabase

def verify_database_schema():
    """Verify all required fields exist in the artists table"""
    client = get_supabase()
    
    print("🔍 VERIFYING DATABASE SCHEMA...")
    print("=" * 50)
    
    try:
        # Get table structure
        result = client.table('artists').select('*').limit(1).execute()
        
        if not result.data:
            print("⚠️ No data in artists table, creating test record...")
            # Create a minimal test record to verify schema
            test_data = {
                'name': 'Test Artist Schema Verification',
                'discovery_source': 'test'
            }
            client.table('artists').insert(test_data).execute()
            result = client.table('artists').select('*').eq('name', 'Test Artist Schema Verification').execute()
        
        current_fields = set(result.data[0].keys())
        
        # Required fields for discovery system
        required_fields = {
            # Basic info
            'id', 'name', 'discovery_date', 'last_updated',
            
            # Discovery metadata
            'discovery_score', 'discovery_source', 'discovery_video_id', 
            'discovery_video_title', 'is_validated', 'last_crawled_at',
            
            # YouTube data
            'youtube_channel_id', 'youtube_channel_url', 'youtube_subscriber_count',
            
            # Spotify comprehensive data
            'spotify_id', 'spotify_url', 'spotify_monthly_listeners', 'spotify_top_city',
            'spotify_biography', 'spotify_genres', 'spotify_followers', 'spotify_popularity_score',
            
            # Instagram data
            'instagram_url', 'instagram_follower_count',
            
            # TikTok data
            'tiktok_url', 'tiktok_follower_count', 'tiktok_likes_count',
            
            # Other social media
            'twitter_url', 'facebook_url', 'website_url',
            
            # Music analysis
            'music_theme_analysis',
            
            # Additional fields
            'avatar_url', 'bio', 'genres', 'location', 'lyrical_themes',
            'metadata', 'social_links', 'follower_counts', 'enrichment_score', 'status'
        }
        
        # Check which fields exist
        existing_fields = current_fields & required_fields
        missing_fields = required_fields - current_fields
        
        print(f"✅ EXISTING FIELDS: {len(existing_fields)}/{len(required_fields)}")
        for field in sorted(existing_fields):
            print(f"  ✓ {field}")
        
        if missing_fields:
            print(f"\n❌ MISSING FIELDS: {len(missing_fields)}")
            for field in sorted(missing_fields):
                print(f"  ✗ {field}")
            print("\n🔧 Run update_artists_table.sql to add missing fields!")
            return False
        else:
            print("\n🎉 ALL REQUIRED FIELDS EXIST!")
            
            # Test a sample insert to verify everything works
            print("\n🧪 TESTING SAMPLE DATA INSERT...")
            test_artist = {
                'name': f'Test Artist {len(result.data)}',
                'discovery_score': 75,
                'discovery_source': 'youtube',
                'spotify_monthly_listeners': 50000,
                'youtube_subscriber_count': 15000,
                'instagram_follower_count': 8000,
                'is_validated': True,
                'spotify_genres': ['pop', 'indie'],
                'music_theme_analysis': 'Love and relationships'
            }
            
            try:
                insert_result = client.table('artists').insert(test_artist).execute()
                if insert_result.data:
                    print("✅ Sample insert successful!")
                    # Clean up test record
                    client.table('artists').delete().eq('id', insert_result.data[0]['id']).execute()
                    print("✅ Test cleanup successful!")
                    return True
                else:
                    print("❌ Sample insert failed!")
                    return False
            except Exception as e:
                print(f"❌ Sample insert error: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Database verification error: {e}")
        return False

if __name__ == "__main__":
    success = verify_database_schema()
    if success:
        print("\n🚀 DATABASE IS READY FOR DISCOVERY SYSTEM!")
    else:
        print("\n⚠️ DATABASE NEEDS UPDATES BEFORE RUNNING DISCOVERY!")