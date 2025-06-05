# Music Artist Discovery System

An AI-powered platform for discovering and enriching emerging music artists using Pydantic AI, FastAPI, React, and Supabase.

## 🎵 Features

- **YouTube Discovery**: Automatically find emerging artists from YouTube
- **Multi-Platform Enrichment**: Gather data from Spotify, Instagram, and web sources
- **AI-Powered Analysis**: Analyze lyrics and content using GPT-4
- **Real-time Updates**: WebSocket integration for live discovery progress
- **Visual Workflow**: Interactive discovery flow visualization
- **Smart Scoring**: Automatic lead scoring based on enrichment data

## 🏗️ Architecture

- **Backend**: FastAPI + Pydantic AI agents
- **Frontend**: React + TypeScript + Tailwind CSS
- **Database**: Supabase (PostgreSQL)
- **Cache**: Redis
- **AI**: OpenAI GPT-4, Firecrawl for web extraction
- **Deployment**: Docker + Coolify

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Supabase account
- API keys for: YouTube, Spotify, OpenAI, Firecrawl

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/music-discovery-system.git
cd music-discovery-system
```

### 2. Set Up Environment Variables

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Required environment variables:
```
YOUTUBE_API_KEY=your_youtube_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
OPENAI_API_KEY=your_openai_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SECRET_KEY=your_secret_key_here
```

### 3. Set Up Supabase Database

1. Create a new Supabase project
2. Run the SQL schema from `supabase-schema.sql` in the SQL editor
3. Copy your project URL and anon key to `.env`

### 4. Run with Docker Compose

```bash
docker-compose up --build
```

This will start:
- Backend API at http://localhost:8000
- Frontend at http://localhost:3000
- Redis at localhost:6379

### 5. Manual Installation (Development)

#### Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```

## 📖 Usage

1. **Start Discovery**: 
   - Navigate to http://localhost:3000
   - Click "Start Discovery" to begin finding artists
   - Monitor progress in real-time

2. **View Artists**:
   - Browse discovered artists in the dashboard
   - Filter by enrichment score
   - Click on an artist for detailed profile

3. **Discovery Flow**:
   - Visit `/discovery` to see the visual workflow
   - Watch as data flows through each stage

## 🔧 API Endpoints

- `POST /api/discover` - Start a new discovery session
- `GET /api/artists` - List discovered artists
- `GET /api/artist/{id}` - Get detailed artist information
- `GET /api/analytics` - Get discovery analytics
- `WS /ws/{client_id}` - WebSocket for real-time updates

## 🏢 Deployment

### Using Coolify

1. Push your code to GitHub
2. In Coolify, create a new application
3. Select "Docker Compose" as the build pack
4. Point to `coolify.yml` in your repository
5. Set all required environment variables
6. Deploy!

### Manual VPS Deployment

1. SSH into your VPS
2. Clone the repository
3. Set up environment variables
4. Run: `docker-compose -f docker-compose.prod.yml up -d`

## 📊 Database Schema

The system uses the following main tables:
- `artists` - Artist profiles with enrichment data
- `videos` - YouTube video metadata
- `lyric_analyses` - AI analysis of song lyrics
- `discovery_sessions` - Discovery run tracking
- `api_rate_limits` - API usage tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Troubleshooting

### Common Issues

1. **YouTube Quota Exceeded**
   - Default quota is 10,000 units/day
   - Request higher quota through Google Console

2. **Spotify Rate Limits**
   - Implement exponential backoff
   - Cache artist data for 24 hours

3. **Memory Issues**
   - Increase Docker memory allocation
   - Process artists in smaller batches

## 🔗 Resources

- [Pydantic AI Documentation](https://ai.pydantic.dev)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Supabase Documentation](https://supabase.com/docs)

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Email: support@musicdiscovery.ai

---

Built with ❤️ for the music industry