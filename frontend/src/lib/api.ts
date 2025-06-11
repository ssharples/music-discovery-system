import { toast } from 'react-hot-toast';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types
export interface Artist {
  id: number;
  name: string;
  youtube_subscriber_count?: number;
  spotify_monthly_listeners?: number;
  instagram_follower_count?: number;
  tiktok_follower_count?: number;
  discovery_score: number;
  genres?: string[];
  discovery_date: string;
  enrichment_score?: number;
  social_links?: Record<string, string>;
  spotify_data?: SpotifyData;
  youtube_data?: YouTubeData;
  instagram_data?: InstagramData;
  tiktok_data?: TikTokData;
  lyrics_analysis?: LyricsAnalysis;
  is_validated?: boolean;
  discovery_source?: string;
  last_crawled_at?: string;
}

export interface SpotifyData {
  monthly_listeners: number;
  followers: number;
  top_tracks: Track[];
  genres: string[];
  bio?: string;
  popularity: number;
}

export interface YouTubeData {
  subscriber_count: number;
  view_count: number;
  video_count: number;
  description?: string;
  thumbnail?: string;
}

export interface InstagramData {
  follower_count: number;
  following_count: number;
  post_count: number;
  bio?: string;
  is_verified?: boolean;
}

export interface TikTokData {
  follower_count: number;
  following_count: number;
  likes_count: number;
  video_count: number;
  bio?: string;
  is_verified?: boolean;
}

export interface Track {
  name: string;
  popularity: number;
  preview_url?: string;
  duration_ms: number;
}

export interface LyricsAnalysis {
  sentiment_score: number;
  themes: string[];
  language: string;
  word_count: number;
  profanity_detected: boolean;
}

export interface DiscoveryRequest {
  search_query: string;
  max_results: number;
  upload_date?: string;
  enable_ai_filtering?: boolean;
  min_discovery_score?: number;
}

export interface DiscoveryResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface DiscoverySession {
  id: string;
  search_query: string;
  max_results: number;
  status: string;
  started_at: string;
  completed_at?: string;
  artists_found: number;
  total_processed: number;
  success_rate: number;
  processing_time_seconds?: number;
}

export interface Analytics {
  total_artists: number;
  high_value_artists: number;
  recent_discoveries: Artist[];
  genre_distribution: GenreStats[];
  api_usage: APIUsage;
  discovery_trends: DiscoveryTrend[];
  platform_metrics: PlatformMetrics;
  quality_metrics: QualityMetrics;
}

export interface GenreStats {
  genre: string;
  count: number;
  percentage: number;
  avg_score: number;
}

export interface APIUsage {
  youtube: {
    requests_made: number;
    quota_limit: number;
    quota_used_percentage: number;
    reset_time?: string;
  };
  spotify: {
    requests_made: number;
    quota_limit: number;
    quota_used_percentage: number;
    reset_time?: string;
  };
}

export interface DiscoveryTrend {
  date: string;
  artists_discovered: number;
  sessions_completed: number;
  avg_quality_score: number;
  total_processing_time: number;
}

export interface PlatformMetrics {
  youtube: {
    total_subscribers: number;
    avg_subscribers: number;
    channels_crawled: number;
  };
  spotify: {
    total_monthly_listeners: number;
    avg_monthly_listeners: number;
    artists_found: number;
  };
  instagram: {
    total_followers: number;
    avg_followers: number;
    profiles_crawled: number;
  };
  tiktok: {
    total_followers: number;
    avg_followers: number;
    profiles_crawled: number;
  };
}

export interface QualityMetrics {
  ai_content_filtered: number;
  human_artists_confirmed: number;
  quality_threshold_met: number;
  artificial_inflation_detected: number;
  validation_rate: number;
}

export interface HealthStatus {
  status: string;
  services: {
    database: boolean;
    redis: boolean;
    youtube_api: boolean;
    spotify_api: boolean;
  };
  version: string;
  uptime: number;
}

// API Client Class
class APIClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      toast.error(`API Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      throw error;
    }
  }

  // Discovery Endpoints
  async startDiscovery(request: DiscoveryRequest): Promise<DiscoveryResponse> {
    return this.request<DiscoveryResponse>('/api/discover', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async startUndiscoveredTalentDiscovery(maxResults: number = 50): Promise<DiscoveryResponse> {
    return this.request<DiscoveryResponse>(`/api/discover/undiscovered-talent?max_results=${maxResults}`, {
      method: 'POST',
    });
  }

  async startMasterDiscovery(maxResults: number = 50, searchQuery: string = 'official music video'): Promise<any> {
    return this.request<any>(`/api/master-discovery/discover?max_results=${maxResults}&search_query=${encodeURIComponent(searchQuery)}`, {
      method: 'POST',
    });
  }

  // Data Retrieval Endpoints
  async getArtists(limit: number = 100, offset: number = 0): Promise<Artist[]> {
    return this.request<Artist[]>(`/api/artists?limit=${limit}&offset=${offset}`);
  }

  async getArtist(id: number): Promise<Artist> {
    return this.request<Artist>(`/api/artist/${id}`);
  }

  async getArtistFullProfile(id: number): Promise<any> {
    return this.request<any>(`/api/discover/artist/${id}/full-profile`);
  }

  // Analytics Endpoints
  async getAnalytics(): Promise<Analytics> {
    return this.request<Analytics>('/api/analytics');
  }

  async getDiscoveryStats(): Promise<any> {
    return this.request<any>('/api/discover/stats/overview');
  }

  async getMasterDiscoveryStatus(): Promise<any> {
    return this.request<any>('/api/master-discovery/status');
  }

  // Session Management
  async getSessions(): Promise<DiscoverySession[]> {
    return this.request<DiscoverySession[]>('/api/sessions');
  }

  async getSession(id: string): Promise<DiscoverySession> {
    return this.request<DiscoverySession>(`/api/session/${id}`);
  }

  async pauseSession(sessionId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/session/${sessionId}/pause`, {
      method: 'POST',
    });
  }

  async resumeSession(sessionId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/session/${sessionId}/resume`, {
      method: 'POST',
    });
  }

  async stopSession(sessionId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/session/${sessionId}/stop`, {
      method: 'POST',
    });
  }

  // Health and Monitoring
  async getHealthStatus(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  // Search and Filtering
  async searchArtists(query: string, filters?: any): Promise<Artist[]> {
    const params = new URLSearchParams({ q: query });
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      });
    }
    return this.request<Artist[]>(`/api/artists/search?${params.toString()}`);
  }

  async getTopArtistsByMetric(metric: string, limit: number = 10): Promise<Artist[]> {
    return this.request<Artist[]>(`/api/artists/top/${metric}?limit=${limit}`);
  }
}

// WebSocket URL Helper
export function getWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`;
  const clientId = Math.random().toString(36).substring(7);
  return `${host}/ws/${clientId}`;
}

// Export singleton instance
export const apiClient = new APIClient();