// frontend/src/lib/api.ts
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Artist {
  id: string;
  name: string;
  youtube_channel_id?: string;
  youtube_channel_name?: string;
  instagram_handle?: string;
  spotify_id?: string;
  email?: string;
  website?: string;
  genres: string[];
  location?: string;
  bio?: string;
  follower_counts: Record<string, number>;
  social_links: Record<string, string>;
  metadata: Record<string, any>;
  discovery_date: string;
  last_updated: string;
  enrichment_score: number;
  status: string;
}

export interface Video {
  id: string;
  artist_id: string;
  youtube_video_id: string;
  title: string;
  description?: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  published_at?: string;
  duration?: number;
  tags: string[];
  captions_available: boolean;
  metadata: Record<string, any>;
}

export interface LyricAnalysis {
  id: string;
  video_id: string;
  artist_id: string;
  themes: string[];
  sentiment_score: number;
  emotional_content: string[];
  lyrical_style?: string;
  subject_matter?: string;
  language: string;
  analysis_metadata: Record<string, any>;
}

export interface DiscoveryRequest {
  search_query: string;
  max_results: number;
  filters?: Record<string, any>;
}

export interface DiscoveryResponse {
  session_id: string;
  status: string;
  message: string;
  artists_found: number;
}

class ApiClient {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  async startDiscovery(request: DiscoveryRequest): Promise<DiscoveryResponse> {
    return this.request<DiscoveryResponse>('/api/discover', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getArtists(params?: {
    skip?: number;
    limit?: number;
    status?: string;
    min_score?: number;
  }): Promise<Artist[]> {
    const queryParams = new URLSearchParams();
    if (params?.skip) queryParams.append('skip', params.skip.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.status) queryParams.append('status', params.status);
    if (params?.min_score) queryParams.append('min_score', params.min_score.toString());
    
    return this.request<Artist[]>(`/api/artists?${queryParams}`);
  }

  async getArtist(id: string): Promise<{
    profile: Artist;
    videos: Video[];
    lyric_analyses: LyricAnalysis[];
    enrichment_score: number;
  }> {
    return this.request(`/api/artist/${id}`);
  }

  async getAnalytics(): Promise<{
    total_artists: number;
    high_value_artists: number;
    recent_discoveries: Artist[];
    genre_distribution: any;
    api_usage: Record<string, any>;
  }> {
    return this.request('/api/analytics');
  }
}

export const api = new ApiClient();

// frontend/src/components/ArtistCard.tsx
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Artist } from '@/lib/api';
import { Instagram, Music, Mail, Globe, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ArtistCardProps {
  artist: Artist;
}

export const ArtistCard: React.FC<ArtistCardProps> = ({ artist }) => {
  const navigate = useNavigate();

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => navigate(`/artist/${artist.id}`)}>
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">{artist.name}</CardTitle>
          <Badge variant={artist.enrichment_score >= 0.7 ? 'default' : 'secondary'}>
            {(artist.enrichment_score * 100).toFixed(0)}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Genres */}
        {artist.genres.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {artist.genres.slice(0, 3).map((genre) => (
              <Badge key={genre} variant="outline" className="text-xs">
                {genre}
              </Badge>
            ))}
          </div>
        )}

        {/* Social Links */}
        <div className="flex gap-2">
          {artist.instagram_handle && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Instagram className="h-3 w-3" />
              <span>{artist.follower_counts.instagram || 0}</span>
            </div>
          )}
          {artist.spotify_id && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Music className="h-3 w-3" />
              <span>{artist.follower_counts.spotify || 0}</span>
            </div>
          )}
        </div>

        {/* Contact Info */}
        <div className="space-y-1">
          {artist.email && (
            <div className="flex items-center gap-1 text-xs">
              <Mail className="h-3 w-3" />
              <span className="truncate">{artist.email}</span>
            </div>
          )}
          {artist.location && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3" />
              <span>{artist.location}</span>
            </div>
          )}
        </div>

        {/* Enrichment Score */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span>Enrichment Score</span>
            <span>{(artist.enrichment_score * 100).toFixed(0)}%</span>
          </div>
          <Progress value={artist.enrichment_score * 100} className="h-2" />
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-4">
          <Button size="sm" variant="outline" className="flex-1" onClick={(e) => {
            e.stopPropagation();
            window.open(`https://youtube.com/channel/${artist.youtube_channel_id}`, '_blank');
          }}>
            YouTube
          </Button>
          {artist.spotify_id && (
            <Button size="sm" variant="outline" className="flex-1" onClick={(e) => {
              e.stopPropagation();
              window.open(`https://open.spotify.com/artist/${artist.spotify_id}`, '_blank');
            }}>
              Spotify
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// frontend/src/components/Navigation.tsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Home, Search, BarChart, Music } from 'lucide-react';

export const Navigation: React.FC = () => {
  const location = useLocation();

  const links = [
    { to: '/', label: 'Dashboard', icon: Home },
    { to: '/discovery', label: 'Discovery Flow', icon: Search },
    { to: '/analytics', label: 'Analytics', icon: BarChart },
  ];

  return (
    <nav className="border-b">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2 font-bold text-xl">
              <Music className="h-6 w-6" />
              Music Discovery
            </Link>
            
            <div className="flex gap-2">
              {links.map((link) => {
                const Icon = link.icon;
                return (
                  <Link key={link.to} to={link.to}>
                    <Button
                      variant={location.pathname === link.to ? 'default' : 'ghost'}
                      size="sm"
                      className="gap-2"
                    >
                      <Icon className="h-4 w-4" />
                      {link.label}
                    </Button>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};

// frontend/package.json
{
  "name": "music-discovery-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-label": "^2.0.2",
    "@radix-ui/react-progress": "^1.0.3",
    "@radix-ui/react-slot": "^1.0.2",
    "@radix-ui/react-tabs": "^1.0.4",
    "@tanstack/react-query": "^5.0.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.0.0",
    "lucide-react": "^0.300.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-hot-toast": "^2.4.1",
    "react-router-dom": "^6.20.0",
    "reactflow": "^11.10.0",
    "tailwind-merge": "^2.0.0",
    "tailwindcss-animate": "^1.0.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.0.0",
    "eslint-plugin-react": "^7.0.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.3.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}

// frontend/.env.example
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000