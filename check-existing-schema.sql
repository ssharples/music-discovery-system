-- Check existing table structures in your Supabase database
-- Run this first to see what tables and columns you currently have

-- Check if tables exist and their structure
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name IN ('artists', 'videos', 'lyric_analyses', 'discovery_sessions')
ORDER BY table_name, ordinal_position;

-- Check existing artists table structure specifically
\d artists;

-- Show existing data in artists table
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'artists' AND table_schema = 'public';

-- Count existing records
SELECT 
  (SELECT COUNT(*) FROM artists) as artist_count,
  (SELECT COUNT(*) FROM videos) as video_count,
  (SELECT COUNT(*) FROM discovery_sessions) as session_count; 