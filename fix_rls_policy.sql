-- Fix Row Level Security Policy for Artists Table
-- Run these commands in your Supabase SQL Editor

-- Option 1: Allow service role to bypass RLS (Recommended for backend services)
-- This allows your backend application to insert/update artists
ALTER TABLE artists FORCE ROW LEVEL SECURITY;

-- Create policy to allow service role (backend) to perform all operations
CREATE POLICY "Allow service role full access to artists" ON artists
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Create policy to allow authenticated users to read artists
CREATE POLICY "Allow authenticated users to read artists" ON artists
FOR SELECT
TO authenticated
USING (true);

-- Option 2: If you want to allow anonymous access (less secure)
-- CREATE POLICY "Allow anonymous read access to artists" ON artists
-- FOR SELECT
-- TO anon
-- USING (true);

-- =============================================================================
-- FIX RECURSIVE TRIGGER ISSUE (STACK DEPTH LIMIT EXCEEDED)
-- =============================================================================

-- Drop the problematic trigger that causes infinite recursion
DROP TRIGGER IF EXISTS update_artist_enrichment_score ON artists;

-- Create a safer trigger that only runs on INSERT (not UPDATE)
CREATE OR REPLACE FUNCTION trigger_update_enrichment_score_safe()
RETURNS TRIGGER AS $$
BEGIN
  -- Only update enrichment score if it's not already set (avoid recursion)
  -- For INSERT triggers, there's no OLD record, only NEW
  IF NEW.enrichment_score = 0.0 OR NEW.enrichment_score IS NULL THEN
    PERFORM update_enrichment_score(NEW.id);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create new trigger that only fires on INSERT to prevent recursion
CREATE TRIGGER update_artist_enrichment_score_safe
AFTER INSERT ON artists
FOR EACH ROW
EXECUTE FUNCTION trigger_update_enrichment_score_safe();

-- Alternative: Update the enrichment score function to not trigger recursion
CREATE OR REPLACE FUNCTION update_enrichment_score(artist_uuid UUID)
RETURNS VOID AS $$
DECLARE
  score FLOAT := 0;
  artist_rec RECORD;
  current_score FLOAT;
BEGIN
  SELECT *, enrichment_score INTO artist_rec, current_score FROM artists WHERE id = artist_uuid;
  
  -- Base score components
  IF artist_rec.youtube_channel_id IS NOT NULL THEN score := score + 0.1; END IF;
  IF artist_rec.instagram_handle IS NOT NULL THEN score := score + 0.15; END IF;
  IF artist_rec.spotify_id IS NOT NULL THEN score := score + 0.15; END IF;
  IF artist_rec.email IS NOT NULL THEN score := score + 0.2; END IF;
  IF artist_rec.website IS NOT NULL THEN score := score + 0.1; END IF;
  IF array_length(artist_rec.genres, 1) > 0 THEN score := score + 0.1; END IF;
  IF artist_rec.bio IS NOT NULL AND length(artist_rec.bio) > 50 THEN score := score + 0.1; END IF;
  
  -- Social metrics bonus (with null checks)
  IF (artist_rec.follower_counts->>'instagram') IS NOT NULL AND 
     (artist_rec.follower_counts->>'instagram')::INTEGER > 1000 THEN 
    score := score + 0.05; 
  END IF;
  IF (artist_rec.follower_counts->>'spotify') IS NOT NULL AND 
     (artist_rec.follower_counts->>'spotify')::INTEGER > 1000 THEN 
    score := score + 0.05; 
  END IF;
  
  -- Only update if score has changed significantly (avoid unnecessary updates)
  IF ABS(current_score - LEAST(score, 1.0)) > 0.01 THEN
    UPDATE artists 
    SET enrichment_score = LEAST(score, 1.0), last_updated = NOW() 
    WHERE id = artist_uuid;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Check existing policies (for debugging)
-- SELECT * FROM pg_policies WHERE tablename = 'artists';

-- If you need to drop existing conflicting policies:
-- DROP POLICY IF EXISTS "old_policy_name" ON artists; 