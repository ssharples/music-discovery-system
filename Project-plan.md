# Music Artist Discovery System - Implementation Plan

## Project Overview
Building a production-ready music artist discovery system using Pydantic AI, FastAPI, React, and Supabase.

## Phase 1: Database Schema Setup
1. Create Supabase tables for:
   - Artists profiles
   - YouTube videos
   - Social media metrics
   - Lyric analysis results
   - Discovery sessions

## Phase 2: Backend Development (Pydantic AI + FastAPI)
1. Core agent architecture:
   - YouTube Discovery Agent
   - Artist Enrichment Agent
   - Lyric Analysis Agent
   - Data Storage Agent

2. API endpoints:
   - `/api/discover` - Trigger discovery process
   - `/api/artists` - Get discovered artists
   - `/api/artist/{id}` - Get detailed artist profile
   - `/api/analytics` - Discovery analytics

## Phase 3: Frontend Development (React + AG-UI)
1. Components:
   - Artist discovery dashboard
   - Real-time discovery visualization
   - Artist profile viewer
   - Analytics dashboard

2. Features:
   - Real-time updates via WebSocket
   - Interactive workflow visualization
   - Filter and search capabilities

## Phase 4: Deployment (Coolify)
1. Dockerize application
2. Setup environment variables
3. Configure Coolify deployment
4. Setup domain and SSL

## Directory Structure
```
music-discovery-system/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── youtube_agent.py
│   │   │   ├── enrichment_agent.py
│   │   │   ├── lyrics_agent.py
│   │   │   └── storage_agent.py
│   │   ├── models/
│   │   │   ├── artist.py
│   │   │   ├── video.py
│   │   │   └── analysis.py
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   └── websocket.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── dependencies.py
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Implementation Steps

### Step 1: Initialize Project
```bash
mkdir music-discovery-system
cd music-discovery-system
git init
```

### Step 2: Setup Backend
```bash
mkdir -p backend/app/{agents,models,api,core}
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

### Step 3: Install Dependencies
```bash
pip install pydantic-ai fastapi uvicorn supabase httpx youtube-transcript-api
pip install python-dotenv tenacity redis celery
```

### Step 4: Create Database Schema
```sql
-- Artists table
CREATE TABLE artists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  youtube_channel_id TEXT UNIQUE,
  youtube_channel_name TEXT,
  instagram_handle TEXT,
  spotify_id TEXT,
  email TEXT,
  website TEXT,
  genres TEXT[],
  location TEXT,
  bio TEXT,
  follower_counts JSONB,
  social_links JSONB,
  metadata JSONB,
  discovery_date TIMESTAMPTZ DEFAULT NOW(),
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  enrichment_score FLOAT DEFAULT 0,
  status TEXT DEFAULT 'discovered'
);

-- Videos table
CREATE TABLE videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artist_id UUID REFERENCES artists(id),
  youtube_video_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  published_at TIMESTAMPTZ,
  duration INTEGER,
  tags TEXT[],
  captions_available BOOLEAN DEFAULT false,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Lyric Analysis table
CREATE TABLE lyric_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID REFERENCES videos(id),
  artist_id UUID REFERENCES artists(id),
  themes TEXT[],
  sentiment_score FLOAT,
  emotional_content TEXT[],
  lyrical_style TEXT,
  subject_matter TEXT,
  language TEXT DEFAULT 'en',
  analysis_metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Discovery Sessions table
CREATE TABLE discovery_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  artists_discovered INTEGER DEFAULT 0,
  videos_processed INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running',
  metadata JSONB
);

-- Create indexes
CREATE INDEX idx_artists_youtube_channel ON artists(youtube_channel_id);
CREATE INDEX idx_artists_status ON artists(status);
CREATE INDEX idx_videos_artist ON videos(artist_id);
CREATE INDEX idx_videos_youtube_id ON videos(youtube_video_id);
```

### Step 5: Environment Variables
```env
# .env file
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
YOUTUBE_API_KEY=your_youtube_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
DEEPSEEK_API_KEY=your_deepseek_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
REDIS_URL=redis://localhost:6379
```

## Next Steps
1. Create Supabase database schema
2. Implement backend agents
3. Build API endpoints
4. Create React frontend
5. Deploy with Coolify