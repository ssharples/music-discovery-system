-- Create missing database functions for the Music Discovery System

-- Function to get genre distribution
CREATE OR REPLACE FUNCTION get_genre_distribution()
RETURNS TABLE(genre TEXT, count BIGINT) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    unnest(genres) as genre,
    COUNT(*) as count
  FROM artists 
  WHERE genres IS NOT NULL AND array_length(genres, 1) > 0
  GROUP BY unnest(genres)
  ORDER BY count DESC
  LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- Add any other missing functions here as needed
-- Function to get API usage stats
CREATE OR REPLACE FUNCTION get_api_usage_stats()
RETURNS TABLE(
  api_name TEXT,
  total_requests BIGINT,
  quota_limit INTEGER,
  usage_percentage NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    arl.api_name,
    SUM(arl.requests_made)::BIGINT as total_requests,
    MAX(arl.quota_limit) as quota_limit,
    CASE 
      WHEN MAX(arl.quota_limit) > 0 THEN 
        ROUND((SUM(arl.requests_made)::NUMERIC / MAX(arl.quota_limit)) * 100, 2)
      ELSE 0
    END as usage_percentage
  FROM api_rate_limits arl
  GROUP BY arl.api_name
  ORDER BY total_requests DESC;
END;
$$ LANGUAGE plpgsql; 