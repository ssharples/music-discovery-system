-- Fresh Music Discovery System Database Schema
-- Run this SQL in your Supabase SQL editor

-- Create the main artist table with all required fields
CREATE TABLE IF NOT EXISTS artist (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    
    -- Basic info
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- YouTube data
    youtube_channel_id VARCHAR(255),
    youtube_subscriber_count BIGINT DEFAULT 0,
    youtube_channel_url VARCHAR(500),
    
    -- Spotify data
    spotify_id VARCHAR(255),
    spotify_url VARCHAR(500),
    spotify_monthly_listeners BIGINT DEFAULT 0,
    spotify_top_city VARCHAR(255),
    spotify_biography TEXT,
    spotify_avatar_url VARCHAR(500),
    spotify_genres JSONB DEFAULT '[]'::jsonb,
    
    -- Instagram data
    instagram_url VARCHAR(500),
    instagram_username VARCHAR(255),
    instagram_follower_count BIGINT DEFAULT 0,
    
    -- TikTok data
    tiktok_url VARCHAR(500),
    tiktok_username VARCHAR(255),
    tiktok_follower_count BIGINT DEFAULT 0,
    tiktok_likes_count BIGINT DEFAULT 0,
    
    -- Other social media
    twitter_url VARCHAR(500),
    facebook_url VARCHAR(500),
    website_url VARCHAR(500),
    
    -- Music analysis
    music_theme_analysis TEXT,
    music_sentiment_tags JSONB DEFAULT '[]'::jsonb,
    
    -- Discovery metadata
    discovery_source VARCHAR(100) DEFAULT 'youtube',
    discovery_video_id VARCHAR(255),
    discovery_video_title VARCHAR(500),
    discovery_score INTEGER DEFAULT 0 CHECK (discovery_score >= 0 AND discovery_score <= 100),
    last_crawled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_validated BOOLEAN DEFAULT FALSE,
    
    -- Constraints
    CONSTRAINT check_follower_counts CHECK (
        instagram_follower_count >= 0 AND 
        tiktok_follower_count >= 0 AND 
        youtube_subscriber_count >= 0 AND
        spotify_monthly_listeners >= 0
    )
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_artist_name ON artist(name);
CREATE INDEX IF NOT EXISTS idx_artist_spotify_id ON artist(spotify_id);
CREATE INDEX IF NOT EXISTS idx_artist_youtube_channel_id ON artist(youtube_channel_id);
CREATE INDEX IF NOT EXISTS idx_artist_discovery_score ON artist(discovery_score DESC);
CREATE INDEX IF NOT EXISTS idx_artist_last_crawled ON artist(last_crawled_at DESC);
CREATE INDEX IF NOT EXISTS idx_artist_is_validated ON artist(is_validated);

-- Create a table for Spotify top tracks
CREATE TABLE IF NOT EXISTS artist_spotify_tracks (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER REFERENCES artist(id) ON DELETE CASCADE,
    track_name VARCHAR(500) NOT NULL,
    track_id VARCHAR(255),
    play_count BIGINT DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    preview_url VARCHAR(500),
    track_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spotify_tracks_artist_id ON artist_spotify_tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_spotify_tracks_play_count ON artist_spotify_tracks(play_count DESC);

-- Create a table for lyrics analysis
CREATE TABLE IF NOT EXISTS artist_lyrics_analysis (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER REFERENCES artist(id) ON DELETE CASCADE,
    song_title VARCHAR(500) NOT NULL,
    lyrics_snippet TEXT, -- First few lines only for analysis
    sentiment_score DECIMAL(3,2), -- -1.0 to 1.0
    themes JSONB DEFAULT '[]'::jsonb,
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lyrics_analysis_artist_id ON artist_lyrics_analysis(artist_id);

-- Create a table for discovery audit trail
CREATE TABLE IF NOT EXISTS artist_discovery_log (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER REFERENCES artist(id) ON DELETE CASCADE,
    discovery_step VARCHAR(100) NOT NULL, -- youtube, spotify, instagram, etc.
    status VARCHAR(50) NOT NULL, -- success, failed, skipped
    data_extracted JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_log_artist_id ON artist_discovery_log(artist_id);
CREATE INDEX IF NOT EXISTS idx_discovery_log_created_at ON artist_discovery_log(created_at DESC);

-- Add table comments
COMMENT ON TABLE artist IS 'Enhanced artist table with comprehensive social media and streaming platform data';
COMMENT ON TABLE artist_spotify_tracks IS 'Top tracks for each artist from Spotify';
COMMENT ON TABLE artist_lyrics_analysis IS 'Sentiment and theme analysis of artist lyrics';
COMMENT ON TABLE artist_discovery_log IS 'Audit trail of the discovery process for each artist';

-- Insert a test record to verify the schema works
INSERT INTO artist (name, discovery_source) VALUES ('Test Artist', 'manual') ON CONFLICT DO NOTHING; 