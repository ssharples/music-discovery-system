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

-- Check existing policies (for debugging)
-- SELECT * FROM pg_policies WHERE tablename = 'artists';

-- If you need to drop existing conflicting policies:
-- DROP POLICY IF EXISTS "old_policy_name" ON artists; 