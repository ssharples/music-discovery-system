-- Update artists table to support all discovery system fields
-- Run this SQL in your Supabase SQL editor

-- Add missing columns to artists table
ALTER TABLE artists 

-- Discovery metadata
ADD COLUMN IF NOT EXISTS discovery_score INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS discovery_source TEXT DEFAULT 'youtube',
ADD COLUMN IF NOT EXISTS discovery_video_id TEXT,
ADD COLUMN IF NOT EXISTS discovery_video_title TEXT,
ADD COLUMN IF NOT EXISTS is_validated BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS last_crawled_at TIMESTAMPTZ DEFAULT NOW(),

-- YouTube data
ADD COLUMN IF NOT EXISTS youtube_channel_url TEXT,
ADD COLUMN IF NOT EXISTS youtube_subscriber_count INTEGER DEFAULT 0,

-- Spotify comprehensive data
ADD COLUMN IF NOT EXISTS spotify_url TEXT,
ADD COLUMN IF NOT EXISTS spotify_monthly_listeners INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS spotify_top_city TEXT,
ADD COLUMN IF NOT EXISTS spotify_biography TEXT,
ADD COLUMN IF NOT EXISTS spotify_genres JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS spotify_followers INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS spotify_popularity_score INTEGER DEFAULT 0,

-- Instagram data
ADD COLUMN IF NOT EXISTS instagram_url TEXT,
ADD COLUMN IF NOT EXISTS instagram_follower_count INTEGER DEFAULT 0,

-- TikTok data
ADD COLUMN IF NOT EXISTS tiktok_url TEXT,
ADD COLUMN IF NOT EXISTS tiktok_follower_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS tiktok_likes_count INTEGER DEFAULT 0,

-- Other social media
ADD COLUMN IF NOT EXISTS twitter_url TEXT,
ADD COLUMN IF NOT EXISTS facebook_url TEXT,
ADD COLUMN IF NOT EXISTS website_url TEXT,

-- Music analysis
ADD COLUMN IF NOT EXISTS music_theme_analysis TEXT;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_artists_discovery_score ON artists(discovery_score);
CREATE INDEX IF NOT EXISTS idx_artists_discovery_source ON artists(discovery_source);
CREATE INDEX IF NOT EXISTS idx_artists_spotify_monthly_listeners ON artists(spotify_monthly_listeners);
CREATE INDEX IF NOT EXISTS idx_artists_is_validated ON artists(is_validated);
CREATE INDEX IF NOT EXISTS idx_artists_last_crawled_at ON artists(last_crawled_at);
CREATE INDEX IF NOT EXISTS idx_artists_youtube_subscriber_count ON artists(youtube_subscriber_count);

-- Add constraints
ALTER TABLE artists 
ADD CONSTRAINT chk_discovery_score CHECK (discovery_score >= 0 AND discovery_score <= 100),
ADD CONSTRAINT chk_spotify_monthly_listeners CHECK (spotify_monthly_listeners >= 0),
ADD CONSTRAINT chk_youtube_subscriber_count CHECK (youtube_subscriber_count >= 0),
ADD CONSTRAINT chk_instagram_follower_count CHECK (instagram_follower_count >= 0),
ADD CONSTRAINT chk_tiktok_follower_count CHECK (tiktok_follower_count >= 0),
ADD CONSTRAINT chk_spotify_popularity_score CHECK (spotify_popularity_score >= 0 AND spotify_popularity_score <= 100);

-- Update existing records to have default values
UPDATE artists 
SET 
    discovery_score = 0,
    discovery_source = 'legacy',
    is_validated = FALSE,
    last_crawled_at = NOW(),
    spotify_monthly_listeners = 0,
    youtube_subscriber_count = 0,
    instagram_follower_count = 0,
    tiktok_follower_count = 0,
    tiktok_likes_count = 0,
    spotify_followers = 0,
    spotify_popularity_score = 0,
    spotify_genres = '[]'::jsonb
WHERE discovery_score IS NULL;

-- Create view for high-value artists
CREATE OR REPLACE VIEW high_value_artists AS
SELECT 
    id,
    name,
    discovery_score,
    spotify_monthly_listeners,
    youtube_subscriber_count,
    instagram_follower_count,
    discovery_date,
    avatar_url,
    spotify_url,
    instagram_url,
    is_validated
FROM artists 
WHERE discovery_score >= 30 
   OR spotify_monthly_listeners >= 10000
   OR youtube_subscriber_count >= 1000
ORDER BY discovery_score DESC, spotify_monthly_listeners DESC;

-- Create view for recent discoveries
CREATE OR REPLACE VIEW recent_discoveries AS
SELECT 
    id,
    name,
    discovery_score,
    spotify_monthly_listeners,
    discovery_date,
    discovery_video_title,
    avatar_url,
    is_validated
FROM artists 
WHERE discovery_date >= NOW() - INTERVAL '30 days'
ORDER BY discovery_date DESC;

-- Grant necessary permissions (adjust as needed for your setup)
GRANT SELECT, INSERT, UPDATE ON artists TO anon;
GRANT SELECT ON high_value_artists TO anon;
GRANT SELECT ON recent_discoveries TO anon;

-- Success message
SELECT 'Artists table successfully updated with all discovery system fields!' as status;