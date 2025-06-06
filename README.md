# 🎵 Music Artist Discovery System

An AI-powered platform for discovering and enriching emerging music artists using Pydantic AI, FastAPI, React, and Supabase.

## 🎯 Overview

This production-ready system uses advanced AI agents to automatically discover emerging music artists by analyzing YouTube videos, extracting lyrical content, and enriching artist profiles with comprehensive metadata. Built for music industry professionals, A&R representatives, and music enthusiasts.

## ✨ Features

### 🔍 Intelligent Discovery
- **YouTube Content Analysis**: Automatically scans YouTube for music videos using configurable search queries
- **Multi-Platform Enrichment**: Gathers data from Instagram, Spotify, and other social platforms
- **AI-Powered Lyric Analysis**: Extracts themes, sentiment, and emotional content from song lyrics
- **Smart Filtering**: Identifies genuine artists vs. covers, remixes, or non-original content

### 📊 Comprehensive Artist Profiles
- **Social Media Metrics**: Follower counts, engagement rates, growth trends
- **Musical Analysis**: Genre classification, lyrical themes, emotional content
- **Contact Information**: Email addresses, website links, social handles
- **Enrichment Scoring**: Automated quality assessment of artist data completeness

### 🤖 AI Agent Architecture
- **YouTube Discovery Agent**: Searches and analyzes YouTube content
- **Enrichment Agent**: Gathers additional artist information from multiple sources
- **Lyrics Analysis Agent**: Processes song lyrics for thematic and emotional content
- **Storage Agent**: Manages data persistence and quality validation
- **Orchestrator Agent**: Coordinates the entire discovery pipeline

### 🔄 Real-Time Processing
- **WebSocket Integration**: Live updates during discovery sessions
- **Background Processing**: Asynchronous task handling with Celery
- **Rate Limiting**: Intelligent API quota management
- **Caching**: Redis-powered performance optimization

## 🏗️ Architecture

### Backend (FastAPI + Pydantic AI)
```
├── app/
│   ├── agents/           # AI agents for discovery and enrichment
│   ├── api/             # REST API endpoints and WebSocket handlers
│   ├── core/            # Configuration and dependencies
│   ├── models/          # Pydantic data models
│   └── main.py          # Application entry point
```

### Frontend (React + TypeScript + Tailwind CSS)
```
├── src/
│   ├── components/      # Reusable UI components
│   ├── pages/          # Application pages
│   ├── contexts/       # React contexts (WebSocket, etc.)
│   ├── lib/            # Utilities and API client
│   └── App.tsx         # Main application component
```

### Database (Supabase/PostgreSQL)
- **Artists**: Core artist profiles and metadata
- **Videos**: YouTube video information and metrics
- **Lyric Analyses**: AI-generated lyrical insights
- **Discovery Sessions**: Track discovery runs and results

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Supabase account
- API keys for YouTube, Spotify, DeepSeek

### 🎯 One-Command Setup (Recommended)

```bash
# Clone and setup everything
git clone <repository-url>
cd music-discovery-system
./setup.sh
```

The setup script will guide you through:
- ✅ Environment configuration
- ✅ Database setup
- ✅ Backend and frontend installation
- ✅ Development environment startup

### 🐳 Docker Deployment

#### Development
```bash
docker-compose up -d
```

#### Production
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### 🌐 Access Points

After setup, access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Monitoring** (Production): http://localhost:9090 (Prometheus), http://localhost:3001 (Grafana)

## 📋 Configuration

### Required API Keys

1. **YouTube Data API v3**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable YouTube Data API v3
   - Create credentials and copy the API key

2. **Spotify API**
   - Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
   - Create an app and get Client ID and Secret

3. **DeepSeek API**
   - Get your API key from [DeepSeek Platform](https://platform.deepseek.com/api_keys)

4. **Supabase**
   - Create a project at [Supabase](https://supabase.com/)
   - Get your project URL and anon key
   - Run the database schema from `database-schema` file

### Environment Configuration

Copy `env.example` to `.env` and configure:

```env
# API Keys
YOUTUBE_API_KEY=your_youtube_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
DEEPSEEK_API_KEY=your_deepseek_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key

# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# Application
SECRET_KEY=your_super_secure_secret_key_at_least_32_characters
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development
DEBUG=true

# Production overrides
# ENVIRONMENT=production
# DEBUG=false
# ALLOWED_ORIGINS=https://yourdomain.com
```

## 🎮 Usage

### Starting a Discovery Session

1. **Navigate to Discovery Page**
   - Open the web interface at http://localhost:3000
   - Go to the "Discovery" section

2. **Configure Search Parameters**
   - Set search query (e.g., "official music video 2024")
   - Choose maximum results (default: 50)
   - Apply filters if needed

3. **Monitor Progress**
   - Watch real-time updates via WebSocket
   - View discovered artists as they're processed
   - Check enrichment scores and data quality

### Analyzing Results

1. **Artist Dashboard**
   - View all discovered artists
   - Sort by enrichment score, discovery date, or genre
   - Filter by status or minimum quality score

2. **Individual Artist Profiles**
   - Detailed social media metrics
   - Lyrical analysis and themes
   - Contact information and links
   - Video performance data

3. **Analytics Overview**
   - Discovery session statistics
   - Genre distribution charts
   - API usage monitoring
   - Performance metrics

## 🔧 API Reference

### Discovery Endpoints
```http
POST /api/discover          # Start discovery session
GET  /api/artists           # List discovered artists
GET  /api/artist/{id}       # Get artist details
GET  /api/analytics         # Get analytics data
GET  /api/sessions          # List discovery sessions
GET  /api/session/{id}      # Get session details
```

### WebSocket Events
```javascript
// Connect to real-time updates
const ws = new WebSocket('ws://localhost:8000/ws/{client_id}');

// Listen for discovery events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle: artist_discovered, enrichment_complete, session_finished
};
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest tests/ -v --cov=app
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

### Integration Tests
```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## 📊 Production Monitoring

### Health Checks
- **Backend**: `GET /health` - Database, Redis, and service status
- **Frontend**: `GET /health` - Application availability
- **Automated**: Docker health checks with restart policies

### Observability Stack
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization dashboards
- **Sentry**: Error tracking and performance monitoring
- **Structured Logging**: JSON logs with correlation IDs

### Key Metrics
- Discovery session success rates
- API quota usage and rate limits
- Response times and error rates
- Database performance
- Cache hit rates

## 🚀 Deployment

### Development
```bash
./setup.sh  # Choose option 4: "Start Development Environment"
```

### Production
```bash
# Using Docker Compose
docker-compose -f docker-compose.prod.yml up -d --build

# Or using the setup script
./setup.sh  # Choose option 5: "Deploy Production Environment"
```

### Cloud Deployment
See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed guides on:
- AWS (ECS, EC2)
- Google Cloud Platform (Cloud Run)
- DigitalOcean (App Platform)
- Azure Container Instances

## 🔒 Security Features

### Production Security
- ✅ Non-root container users
- ✅ Security headers (CSP, HSTS, etc.)
- ✅ Rate limiting and DDoS protection
- ✅ Input validation and sanitization
- ✅ Secrets management
- ✅ HTTPS enforcement
- ✅ Database connection encryption

### Development Security
- Environment variable validation
- API key rotation support
- Audit logging
- CORS configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript for frontend development
- Write tests for new features
- Update documentation as needed
- Use conventional commits

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Quick Setup**: Use `./setup.sh` for guided installation
- **Documentation**: Check [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guides
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions and ideas

## 🔮 Roadmap

### ✅ Phase 1 (Completed)
- [x] Core discovery pipeline with AI agents
- [x] YouTube content analysis and enrichment
- [x] Real-time WebSocket updates
- [x] Production-ready deployment
- [x] Comprehensive monitoring and observability
- [x] Security hardening

### 🚧 Phase 2 (In Progress)
- [ ] TikTok integration for viral content discovery
- [ ] Advanced sentiment analysis with emotion detection
- [ ] Machine learning recommendations engine
- [ ] Data export functionality (CSV, JSON, API)

### 🔮 Phase 3 (Planned)
- [ ] Mobile application (React Native)
- [ ] Real-time trend detection and alerts
- [ ] Industry partnership integrations
- [ ] Advanced analytics dashboard with custom metrics

---

**Built with ❤️ for the music industry**

*Ready for production deployment with enterprise-grade monitoring, security, and scalability.*