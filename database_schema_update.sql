-- Database Schema Update for Music Discovery System
-- Run this in your Supabase SQL editor to add missing tables

-- Create discovery sessions table if it doesn't exist
CREATE TABLE IF NOT EXISTS discovery_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_query VARCHAR(500) NOT NULL,
    max_results INTEGER DEFAULT 50,
    filters JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'started',
    results JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    artists_found INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0
);

-- Add indexes for discovery sessions
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_started_at ON discovery_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status ON discovery_sessions(status);

-- Add comment
COMMENT ON TABLE discovery_sessions IS 'Discovery session tracking with results and metadata';

-- Check if artist table exists, create if not (fallback)
CREATE TABLE IF NOT EXISTS artist (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    youtube_channel_id VARCHAR(255),
    youtube_subscriber_count BIGINT DEFAULT 0,
    youtube_channel_url VARCHAR(500),
    spotify_id VARCHAR(255),
    spotify_url VARCHAR(500),
    spotify_monthly_listeners BIGINT DEFAULT 0,
    spotify_top_city VARCHAR(255),
    spotify_biography TEXT,
    spotify_avatar_url VARCHAR(500),
    spotify_genres JSONB DEFAULT '[]'::jsonb,
    instagram_url VARCHAR(500),
    instagram_username VARCHAR(255),
    instagram_follower_count BIGINT DEFAULT 0,
    tiktok_url VARCHAR(500),
    tiktok_username VARCHAR(255),
    tiktok_follower_count BIGINT DEFAULT 0,
    tiktok_likes_count BIGINT DEFAULT 0,
    twitter_url VARCHAR(500),
    facebook_url VARCHAR(500),
    website_url VARCHAR(500),
    music_theme_analysis TEXT,
    music_sentiment_tags JSONB DEFAULT '[]'::jsonb,
    discovery_source VARCHAR(100) DEFAULT 'youtube',
    discovery_video_id VARCHAR(255),
    discovery_video_title VARCHAR(500),
    discovery_score INTEGER DEFAULT 0 CHECK (discovery_score >= 0 AND discovery_score <= 100),
    last_crawled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_validated BOOLEAN DEFAULT FALSE,
    CONSTRAINT check_follower_counts CHECK (
        instagram_follower_count >= 0 AND 
        tiktok_follower_count >= 0 AND 
        youtube_subscriber_count >= 0 AND
        spotify_monthly_listeners >= 0
    )
);

-- Add indexes for artist table
CREATE INDEX IF NOT EXISTS idx_artist_name ON artist(name);
CREATE INDEX IF NOT EXISTS idx_artist_spotify_id ON artist(spotify_id);
CREATE INDEX IF NOT EXISTS idx_artist_youtube_channel_id ON artist(youtube_channel_id);
CREATE INDEX IF NOT EXISTS idx_artist_discovery_score ON artist(discovery_score DESC);
CREATE INDEX IF NOT EXISTS idx_artist_last_crawled ON artist(last_crawled_at DESC);
CREATE INDEX IF NOT EXISTS idx_artist_is_validated ON artist(is_validated);

-- Verify tables exist
SELECT 
    'discovery_sessions' as table_name,
    COUNT(*) as record_count 
FROM discovery_sessions
UNION ALL
SELECT 
    'artist' as table_name,
    COUNT(*) as record_count 
FROM artist; 