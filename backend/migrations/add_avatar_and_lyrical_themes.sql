-- Migration: Add avatar_url and lyrical_themes columns to artists table
-- Date: 2025-01-06

-- Add avatar_url column to store artist profile image
ALTER TABLE artists 
ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Add lyrical_themes column to store consolidated themes from lyric analyses
ALTER TABLE artists 
ADD COLUMN IF NOT EXISTS lyrical_themes TEXT[];

-- Create index on lyrical_themes for searching
CREATE INDEX IF NOT EXISTS idx_artists_lyrical_themes 
ON artists USING GIN (lyrical_themes);

-- Update the enrichment score function to include avatar and themes
CREATE OR REPLACE FUNCTION update_enrichment_score(artist_uuid UUID)
RETURNS VOID AS $$
DECLARE
  score FLOAT := 0;
  artist_rec RECORD;
  current_score FLOAT;
BEGIN
  SELECT * INTO artist_rec FROM artists WHERE id = artist_uuid;
  current_score := artist_rec.enrichment_score;
  
  -- Base score components
  IF artist_rec.youtube_channel_id IS NOT NULL THEN score := score + 0.1; END IF;
  IF artist_rec.instagram_handle IS NOT NULL THEN score := score + 0.15; END IF;
  IF artist_rec.spotify_id IS NOT NULL THEN score := score + 0.15; END IF;
  IF artist_rec.email IS NOT NULL THEN score := score + 0.2; END IF;
  IF artist_rec.website IS NOT NULL THEN score := score + 0.1; END IF;
  IF array_length(artist_rec.genres, 1) > 0 THEN score := score + 0.1; END IF;
  IF artist_rec.bio IS NOT NULL AND length(artist_rec.bio) > 50 THEN score := score + 0.1; END IF;
  
  -- New scoring components
  IF artist_rec.avatar_url IS NOT NULL THEN score := score + 0.05; END IF;
  IF array_length(artist_rec.lyrical_themes, 1) > 0 THEN score := score + 0.05; END IF;
  
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

-- Grant permissions if needed
GRANT SELECT, INSERT, UPDATE ON artists TO authenticated;
GRANT SELECT, INSERT, UPDATE ON artists TO service_role; 