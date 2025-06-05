// API Configuration - Use relative URLs since nginx proxies to backend
const API_BASE_URL = '';

// Helper function to get the appropriate WebSocket URL
export const getWebSocketUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  return `${protocol}//${window.location.host}/ws/${clientId}`;
};

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
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async startDiscovery(request: DiscoveryRequest): Promise<DiscoveryResponse> {
    return this.request<DiscoveryResponse>('/api/discovery/start', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getDiscoverySessions(): Promise<any[]> {
    return this.request<any[]>('/api/sessions');
  }

  async getSessionDetails(sessionId: string): Promise<any> {
    return this.request<any>(`/api/session/${sessionId}`);
  }

  async getApiQuota(): Promise<any> {
    return this.request<any>('/api/analytics/quota');
  }

  async getArtists(params?: {
    skip?: number;
    limit?: number;
    status?: string;
    min_score?: number;
  }): Promise<Artist[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.status) searchParams.append('status', params.status);
    if (params?.min_score) searchParams.append('min_score', params.min_score.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `/api/artists?${queryString}` : '/api/artists';
    
    return this.request<Artist[]>(endpoint);
  }

  async getArtist(id: string): Promise<{
    profile: Artist;
    videos: Video[];
    lyric_analyses: LyricAnalysis[];
    enrichment_score: number;
  }> {
    return this.request(`/api/artists/${id}`);
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

// Export singleton instance
export const apiClient = new ApiClient();

// Also export as default for backwards compatibility
export default apiClient;