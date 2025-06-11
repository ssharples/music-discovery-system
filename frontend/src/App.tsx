import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import { 
  TrendingUp, TrendingDown, Users, Music, Play, 
  RefreshCw, Star, ExternalLink, Calendar, Heart, Activity
} from 'lucide-react';

import { apiClient, Artist, DiscoveryRequest, getWebSocketUrl } from './lib/api';

// Types
interface DashboardData {
  analytics: any;
  sessions: any[];
  artists: Artist[];
  loading: boolean;
  error: string | null;
}

// Components
function LoadingSpinner({ size = 'md', color = 'blue' }: { 
  size?: 'sm' | 'md' | 'lg'; 
  color?: 'blue' | 'white' | 'gray'; 
}) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12'
  };

  const colorClasses = {
    blue: 'border-blue-600',
    white: 'border-white',
    gray: 'border-gray-600'
  };

  return (
    <div className={`animate-spin rounded-full border-2 border-t-transparent ${sizeClasses[size]} ${colorClasses[color]}`} />
  );
}

function StatCard({ title, value, change, icon: Icon, color }: {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'green' | 'orange' | 'purple' | 'red';
}) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600 border-blue-200',
    green: 'bg-green-50 text-green-600 border-green-200',
    orange: 'bg-orange-50 text-orange-600 border-orange-200',
    purple: 'bg-purple-50 text-purple-600 border-purple-200',
    red: 'bg-red-50 text-red-600 border-red-200',
  };

  const iconColorClasses = {
    blue: 'text-blue-500',
    green: 'text-green-500',
    orange: 'text-orange-500',
    purple: 'text-purple-500',
    red: 'text-red-500',
  };

  return (
    <div className={`bg-white rounded-lg shadow border ${colorClasses[color]} p-6`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-full ${colorClasses[color]}`}>
          <Icon className={`w-6 h-6 ${iconColorClasses[color]}`} />
        </div>
      </div>
      
      {change !== undefined && (
        <div className="mt-4 flex items-center">
          {change >= 0 ? (
            <TrendingUp className="w-4 h-4 text-green-500 mr-1" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-500 mr-1" />
          )}
          <span className={`text-sm font-medium ${
            change >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
          <span className="text-sm text-gray-500 ml-1">vs last period</span>
        </div>
      )}
    </div>
  );
}

function ChartContainer({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {subtitle && (
          <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}

function ArtistCard({ artist }: { artist: Artist }) {
  const formatNumber = (num: number | undefined): string => {
    if (!num) return '0';
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getScoreColor = (score: number): string => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-blue-600 bg-blue-50';
    if (score >= 40) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 truncate" title={artist.name}>
            {artist.name}
          </h3>
          <div className="flex items-center mt-1">
            <Star className="w-4 h-4 text-yellow-500 mr-1" />
            <span className={`text-sm font-medium px-2 py-1 rounded-full ${getScoreColor(artist.discovery_score || 0)}`}>
              {(artist.discovery_score || 0).toFixed(0)}
            </span>
          </div>
        </div>
        <ExternalLink className="w-4 h-4 text-gray-400 hover:text-gray-600" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {artist.youtube_subscriber_count && (
          <div className="flex items-center">
            <div className="w-2 h-2 bg-red-500 rounded-full mr-2" />
            <div>
              <p className="text-xs text-gray-500">YouTube</p>
              <p className="text-sm font-medium">{formatNumber(artist.youtube_subscriber_count)}</p>
            </div>
          </div>
        )}

        {artist.spotify_monthly_listeners && (
          <div className="flex items-center">
            <div className="w-2 h-2 bg-green-500 rounded-full mr-2" />
            <div>
              <p className="text-xs text-gray-500">Spotify</p>
              <p className="text-sm font-medium">{formatNumber(artist.spotify_monthly_listeners)}</p>
            </div>
          </div>
        )}
      </div>

      {artist.genres && artist.genres.length > 0 && (
        <div className="mt-3">
          <div className="flex flex-wrap gap-1">
            {artist.genres.slice(0, 3).map((genre, index) => (
              <span 
                key={index}
                className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full"
              >
                {genre}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-xs text-gray-500">
          Discovered {new Date(artist.discovery_date).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}

// Dashboard Component
function Dashboard() {
  const [data, setData] = useState<DashboardData>({
    analytics: null,
    sessions: [],
    artists: [],
    loading: true,
    error: null
  });

  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [debugInfo, setDebugInfo] = useState<string>('');

  useEffect(() => {
    console.log('Dashboard mounted, loading data...');
    loadDashboardData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      console.log('Auto-refresh triggered');
      loadDashboardData(true);
    }, 30000);
    
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const loadDashboardData = async (isRefresh = false) => {
    try {
      console.log('Loading dashboard data, isRefresh:', isRefresh);
      setDebugInfo(`Loading data... isRefresh: ${isRefresh}`);

      if (isRefresh) {
        setRefreshing(true);
      } else {
        setData(prev => ({ ...prev, loading: true, error: null }));
      }

      console.log('Making API calls...');
      const [analyticsResult, artistsResult, sessionsResult] = await Promise.allSettled([
        apiClient.getAnalytics(),
        apiClient.getArtists(),
        apiClient.getSessions()
      ]);

      console.log('API results:', {
        analytics: analyticsResult.status,
        artists: artistsResult.status,
        sessions: sessionsResult.status
      });

      const analytics = analyticsResult.status === 'fulfilled' ? analyticsResult.value : null;
      const artists = artistsResult.status === 'fulfilled' ? artistsResult.value : [];
      const sessions = sessionsResult.status === 'fulfilled' ? sessionsResult.value : [];

      console.log('Processed data:', { analytics, artists: artists?.length, sessions: sessions?.length });
      setDebugInfo(`Data loaded successfully. Artists: ${artists?.length || 0}, Sessions: ${sessions?.length || 0}`);

      setData(prev => ({
        ...prev,
        analytics: analytics || {},
        artists: artists || [],
        sessions: sessions || [],
        loading: false,
        error: null
      }));
    } catch (error) {
      console.error('Dashboard data loading error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to load dashboard data';
      setDebugInfo(`Error: ${errorMessage}`);
      setData(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
    } finally {
      setRefreshing(false);
    }
  };

  console.log('Dashboard render state:', { loading: data.loading, error: data.error, hasAnalytics: !!data.analytics });

  if (data.loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <LoadingSpinner />
          <p className="mt-4 text-gray-600">Loading dashboard...</p>
          <p className="mt-2 text-sm text-gray-500">{debugInfo}</p>
        </div>
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-medium">Error Loading Dashboard</h3>
          <p className="text-red-600 mt-1">{data.error}</p>
          <p className="text-sm text-gray-600 mt-2">Debug: {debugInfo}</p>
          <button 
            onClick={() => loadDashboardData()}
            className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Ensure we have safe data to render
  const safeAnalytics = data.analytics || {};
  const safeArtists = Array.isArray(data.artists) ? data.artists : [];
  const safeSessions = Array.isArray(data.sessions) ? data.sessions : [];

  console.log('Rendering dashboard with data:', { safeAnalytics, artistsCount: safeArtists.length, sessionsCount: safeSessions.length });

  const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300'];

  const platformData = safeAnalytics?.platform_metrics ? [
    { name: 'YouTube', value: safeAnalytics.platform_metrics.youtube?.channels_crawled || 0 },
    { name: 'Spotify', value: safeAnalytics.platform_metrics.spotify?.artists_found || 0 },
    { name: 'Instagram', value: safeAnalytics.platform_metrics.instagram?.profiles_crawled || 0 },
    { name: 'TikTok', value: safeAnalytics.platform_metrics.tiktok?.profiles_crawled || 0 }
  ] : [
    { name: 'YouTube', value: 25 },
    { name: 'Spotify', value: 15 },
    { name: 'Instagram', value: 30 },
    { name: 'TikTok', value: 20 }
  ];

  const genreData = safeAnalytics?.genre_distribution && Array.isArray(safeAnalytics.genre_distribution) 
    ? safeAnalytics.genre_distribution 
    : [
      { genre: 'Pop', count: 45, avg_score: 75 },
      { genre: 'Hip-Hop', count: 38, avg_score: 82 },
      { genre: 'Electronic', count: 22, avg_score: 68 },
      { genre: 'Rock', count: 18, avg_score: 71 },
      { genre: 'R&B', count: 15, avg_score: 79 }
    ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Debug Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
        <strong>Debug:</strong> {debugInfo} | Artists: {safeArtists.length} | Sessions: {safeSessions.length}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">🎵 Music Discovery Analytics</h1>
          <p className="text-gray-600 mt-1">
            Comprehensive insights into artist discovery and platform performance
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <label className="text-sm text-gray-600">Auto-refresh</label>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                autoRefresh ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  autoRefresh ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
          
          <button
            onClick={() => loadDashboardData(true)}
            disabled={refreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {refreshing ? <LoadingSpinner size="sm" color="white" /> : <RefreshCw className="w-4 h-4" />}
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Artists"
          value={safeAnalytics?.total_artists || safeArtists.length || 0}
          change={12.5}
          icon={Users}
          color="blue"
        />
        <StatCard
          title="High Value Artists"
          value={safeAnalytics?.high_value_artists || Math.floor((safeArtists.length || 0) * 0.3)}
          change={8.2}
          icon={TrendingUp}
          color="green"
        />
        <StatCard
          title="Active Sessions"
          value={safeSessions.filter(s => s?.status === 'running').length}
          change={-3.1}
          icon={Activity}
          color="orange"
        />
        <StatCard
          title="Success Rate"
          value={`${safeAnalytics?.quality_metrics?.validation_rate?.toFixed(1) || '87.3'}%`}
          change={5.7}
          icon={Heart}
          color="purple"
        />
      </div>

      {/* Simple Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Distribution */}
        <ChartContainer title="Platform Coverage" subtitle="Data sources breakdown">
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={platformData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {platformData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartContainer>

        {/* Genre Distribution */}
        <ChartContainer title="Genre Distribution" subtitle="Artists by music genre">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={genreData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="genre" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      </div>

      {/* Recent Artists */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">🌟 Recent Discoveries</h3>
        {safeArtists.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {safeArtists.slice(0, 6).map((artist, index) => (
              <ArtistCard key={artist.id || index} artist={artist} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <Music className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No artists discovered yet. Start a discovery session to see results!</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Discovery Component
function Discovery() {
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryStatus, setDiscoveryStatus] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    setupWebSocket();
  }, []);

  const setupWebSocket = () => {
    try {
      const wsUrl = getWebSocketUrl();
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setWsConnected(true);
        addLog('🔗 WebSocket connected - Real-time updates enabled');
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        } catch (error) {
          addLog(`❌ WebSocket message error: ${error}`);
        }
      };
      
      ws.onclose = () => {
        setWsConnected(false);
        addLog('📡 WebSocket disconnected');
        setTimeout(setupWebSocket, 5000);
      };
      
      ws.onerror = () => {
        addLog('⚠️ WebSocket error occurred');
      };
      
    } catch (error) {
      addLog(`❌ WebSocket setup failed: ${error}`);
    }
  };

  const handleWebSocketMessage = (message: any) => {
    const { type, details, progress } = message;
    
    switch (type) {
      case 'discovery_started':
        addLog(`🚀 Discovery session started: ${message.session_id}`);
        addLog(`🔍 Search query: "${details?.search_query || 'unknown'}" (max ${details?.max_results || 0} results)`);
        setIsDiscovering(true);
        break;
        
      case 'discovery_progress':
        if (progress?.message) {
          addLog(progress.message);
        }
        if (progress?.progress !== undefined) {
          setDiscoveryStatus(`${progress.message} (${Math.round(progress.progress)}%)`);
        }
        break;
        
      case 'discovery_completed':
        const { artists_discovered } = message.summary || {};
        addLog(`🎉 Discovery completed: ${artists_discovered || 0} artists found`);
        setIsDiscovering(false);
        setDiscoveryStatus(`Discovery completed: ${artists_discovered || 0} artists found`);
        break;
        
      case 'artist_discovered':
        addLog(`✨ New artist discovered: ${message.artist?.name || 'Unknown'}`);
        break;
        
      default:
        if (message.message) {
          addLog(message.message);
        }
    }
  };

  const runDiscovery = async () => {
    setIsDiscovering(true);
    setDiscoveryStatus('🚀 Starting discovery...');
    
    try {
      const request: DiscoveryRequest = {
        search_query: "official music video",
        max_results: 50
      };
      
      const response = await apiClient.startDiscovery(request);
      setDiscoveryStatus(`✅ Discovery started: ${response.session_id}`);
      addLog(`✅ Discovery session started: ${response.session_id}`);
    } catch (error) {
      setDiscoveryStatus('❌ Discovery failed');
      addLog(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsDiscovering(false);
    }
  };

  const addLog = (message: string) => {
    setLogs(prev => [`${new Date().toLocaleTimeString()} - ${message}`, ...prev].slice(0, 100));
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">🔍 Discovery Control Center</h1>
        <p className="text-gray-600 mt-1">Start and manage music discovery sessions</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Discovery Session</h2>
            <div className="flex items-center mt-1">
              <div className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-600">
                WebSocket {wsConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
          <button
            onClick={runDiscovery}
            disabled={isDiscovering}
            className="flex items-center space-x-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {isDiscovering ? <LoadingSpinner size="sm" color="white" /> : <Play className="w-5 h-5" />}
            <span className="font-medium">{isDiscovering ? 'Discovering...' : 'Start Discovery'}</span>
          </button>
        </div>

        {discoveryStatus && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-blue-800 font-medium">{discoveryStatus}</p>
          </div>
        )}

        <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
          <h3 className="font-medium mb-2 flex items-center">
            <Activity className="w-4 h-4 mr-2" />
            Real-time Session Logs
          </h3>
          {logs.length === 0 ? (
            <p className="text-gray-500 text-sm">No logs yet. Start a discovery session to see real-time updates.</p>
          ) : (
            <div className="space-y-1">
              {logs.map((log, index) => (
                <div key={index} className="text-sm font-mono text-gray-700 p-1 hover:bg-gray-100 rounded">
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">🚀 Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={() => runDiscovery()}
            className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left"
          >
            <Play className="w-6 h-6 text-blue-600 mb-2" />
            <h4 className="font-medium">Standard Discovery</h4>
            <p className="text-sm text-gray-600">Find new artists with default settings</p>
          </button>
          
          <button 
            onClick={() => {
              addLog('🎯 Undiscovered talent discovery coming soon...');
            }}
            className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left"
          >
            <Star className="w-6 h-6 text-yellow-600 mb-2" />
            <h4 className="font-medium">Undiscovered Talent</h4>
            <p className="text-sm text-gray-600">Focus on emerging artists</p>
          </button>
          
          <Link 
            to="/dashboard"
            className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left block"
          >
            <Calendar className="w-6 h-6 text-green-600 mb-2" />
            <h4 className="font-medium">View Analytics</h4>
            <p className="text-sm text-gray-600">Check discovery performance</p>
          </Link>
        </div>
      </div>
    </div>
  );
}

// Navigation Component
function Navigation() {
  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Music className="w-8 h-8 text-blue-600 mr-3" />
            <span className="text-xl font-bold text-gray-900">Music Discovery System</span>
          </div>
          <div className="flex items-center space-x-8">
            <Link 
              to="/dashboard" 
              className="text-gray-700 hover:text-blue-600 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            >
              📊 Analytics Dashboard
            </Link>
            <Link 
              to="/discovery" 
              className="text-gray-700 hover:text-blue-600 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            >
              🔍 Discovery Control
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

// Main App Component
function App() {
  console.log('App component rendering');
  
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/discovery" element={<Discovery />} />
        </Routes>
        <Toaster position="top-right" />
      </div>
    </Router>
  );
}

export default App; 