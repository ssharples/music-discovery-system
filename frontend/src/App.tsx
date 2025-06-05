import { useState, useEffect } from 'react';
import { apiClient, Artist, DiscoveryRequest, getWebSocketUrl } from './lib/api';

function App() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryStatus, setDiscoveryStatus] = useState('');
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    fetchHealthStatus();
    fetchArtists();
    fetchAnalytics();
    fetchSessions();
    setupWebSocket();
    
    // Refresh data every 30 seconds
    const interval = setInterval(() => {
      fetchHealthStatus();
      fetchAnalytics();
      fetchSessions();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const setupWebSocket = () => {
    try {
      const wsUrl = getWebSocketUrl();
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setWsConnected(true);
        addLog('WebSocket connected - Real-time updates enabled');
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        } catch (error) {
          addLog(`WebSocket message error: ${error}`);
        }
      };
      
      ws.onclose = () => {
        setWsConnected(false);
        addLog('WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(setupWebSocket, 5000);
      };
      
      ws.onerror = (error) => {
        addLog(`WebSocket error: ${error}`);
      };
      
    } catch (error) {
      addLog(`WebSocket setup failed: ${error}`);
    }
  };

  const handleWebSocketMessage = (message: any) => {
    const { type, session_id, details, progress, summary } = message;
    
    switch (type) {
      case 'connection':
        addLog('🔗 WebSocket connected - Real-time updates enabled');
        break;
        
      case 'discovery_started':
        addLog(`🚀 Discovery session started: ${session_id}`);
        addLog(`🔍 Search query: "${details?.search_query || 'unknown'}" (max ${details?.max_results || 0} results)`);
        setCurrentSessionId(session_id);
        fetchSessions();
        break;
        
      case 'discovery_progress':
        if (progress?.message) {
          addLog(progress.message);
        }
        
        // Update discovery status with progress
        if (progress?.progress !== undefined) {
          setDiscoveryStatus(`${progress.message} (${Math.round(progress.progress)}%)`);
        }
        
        // Handle specific progress phases
        switch (progress?.phase) {
          case 'youtube_discovery':
            addLog(`🔍 Searching YouTube...`);
            break;
          case 'youtube_discovery_complete':
            addLog(`✅ Found ${progress.artists_found || 0} potential artists`);
            break;
          case 'artist_processing':
            addLog(`🎤 Starting artist enrichment pipeline...`);
            break;
          case 'processing_artist':
            if (progress.current_artist) {
              addLog(`🔍 Processing: ${progress.current_artist}`);
            }
            break;
          case 'artist_processed':
            if (progress.enriched_count) {
              addLog(`✅ Successfully enriched ${progress.enriched_count} artists so far`);
            }
            break;
          case 'artist_skipped':
            addLog(`⚠️ Skipped artist (insufficient data)`);
            break;
          case 'artist_error':
            addLog(`❌ Error: ${progress.error || 'Unknown error'}`);
            break;
          case 'pipeline_error':
            addLog(`💥 Pipeline failed: ${progress.error || 'Unknown error'}`);
            setIsDiscovering(false);
            break;
        }
        break;
        
      case 'discovery_completed':
        const { artists_discovered, videos_processed, total_candidates, success_rate } = summary || {};
        addLog(`🎉 Discovery completed!`);
        addLog(`📊 Results: ${artists_discovered || 0} artists enriched from ${total_candidates || 0} candidates`);
        addLog(`📹 ${videos_processed || 0} videos processed | Success rate: ${success_rate || '0%'}`);
        
        setIsDiscovering(false);
        setDiscoveryStatus(`Discovery completed: ${artists_discovered || 0} artists found`);
        fetchSessions();
        fetchArtists();
        fetchAnalytics();
        break;
        
      case 'artist_discovered':
        if (details?.name) {
          addLog(`🎤 New artist discovered: ${details.name} (score: ${details.enrichment_score?.toFixed(2) || 'N/A'})`);
          // Trigger a refresh of artists list
          fetchArtists();
        }
        break;
        
      default:
        addLog(`📨 ${type}: ${JSON.stringify(message).substring(0, 100)}...`);
    }
  };

  const fetchHealthStatus = async () => {
    try {
      const response = await fetch('/health');
      const health = await response.json();
      setHealthStatus(health);
      addLog(`Health check: ${health.status}`);
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus({ status: 'error', error: 'Connection failed' });
      addLog(`Health check failed: ${error}`);
    }
  };

  const fetchArtists = async () => {
    try {
      const artistList = await apiClient.getArtists({ limit: 20 });
      setArtists(artistList);
      addLog(`Loaded ${artistList.length} artists`);
    } catch (error) {
      console.error('Failed to fetch artists:', error);
      addLog(`Failed to fetch artists: ${error}`);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const analyticsData = await apiClient.getAnalytics();
      setAnalytics(analyticsData);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      addLog(`Failed to fetch analytics: ${error}`);
    }
  };

  const fetchSessions = async () => {
    try {
      const sessionsData = await apiClient.getDiscoverySessions();
      setSessions(sessionsData);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
      addLog(`Failed to fetch sessions: ${error}`);
    }
  };

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev.slice(0, 49)]); // Keep last 50 logs
  };

  const runDiscovery = async () => {
    setIsDiscovering(true);
    setDiscoveryStatus('Starting discovery for "official music video"...');
    addLog('Starting discovery session');

    try {
      const request: DiscoveryRequest = {
        search_query: 'official music video',
        max_results: 50
      };

      const response = await apiClient.startDiscovery(request);
      setDiscoveryStatus(`Discovery started: ${response.message}`);
      setCurrentSessionId(response.session_id);
      addLog(`🚀 Discovery session started: ${response.session_id}`);
      
      // Check progress every 10 seconds
      const checkProgress = setInterval(async () => {
        try {
          await fetchArtists();
          await fetchAnalytics();
        } catch (error) {
          addLog(`Progress check failed: ${error}`);
        }
      }, 10000);

      // Stop checking after 5 minutes
      setTimeout(() => {
        clearInterval(checkProgress);
        setIsDiscovering(false);
        setDiscoveryStatus('Discovery session completed');
        addLog('Discovery session completed');
        fetchArtists();
        fetchAnalytics();
      }, 300000);

    } catch (error) {
      console.error('Discovery failed:', error);
      setDiscoveryStatus(`Discovery failed: ${error}`);
      addLog(`Discovery failed: ${error}`);
      setIsDiscovering(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">
          🎛️ Music Discovery Admin Dashboard
        </h1>

        {/* System Status Grid */}
        <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Health Status */}
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">System Health</h2>
              <div className={`w-3 h-3 rounded-full ${
                healthStatus?.status === 'healthy' ? 'bg-green-500' :
                healthStatus?.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
              }`}></div>
            </div>
            
            {healthStatus?.services && (
              <div className="space-y-2">
                {Object.entries(healthStatus.services).map(([service, status]) => (
                  <div key={service} className="flex justify-between text-sm">
                    <span className="capitalize">{service}:</span>
                    <span className={`font-medium ${
                      status === 'operational' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {status as string}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* WebSocket Status */}
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Real-time Updates</h2>
              <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            </div>
            <div className="text-sm text-gray-600">
              <div>WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}</div>
              <div>Live monitoring: {wsConnected ? 'Active' : 'Offline'}</div>
            </div>
          </div>

          {/* Current Session */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-4">Current Session</h2>
            <div className="text-sm text-gray-600">
              {currentSessionId ? (
                <div>
                  <div className="font-mono text-xs">{currentSessionId}</div>
                  <div className={`mt-2 inline-block px-2 py-1 rounded text-xs ${
                    isDiscovering ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {isDiscovering ? 'Running' : 'Completed'}
                  </div>
                </div>
              ) : (
                <div>No active session</div>
              )}
            </div>
          </div>
        </div>

        {/* Discovery Controls */}
        <div className="mb-8 p-6 bg-white rounded-lg shadow">
          <h2 className="text-2xl font-semibold mb-4">Discovery Control</h2>
          <p className="text-gray-600 mb-4">Run automated discovery for "official music video" search query</p>
          
          <div className="flex items-center gap-4 mb-4">
            <button
              onClick={runDiscovery}
              disabled={isDiscovering}
              className={`px-8 py-3 rounded-lg font-medium text-lg ${
                isDiscovering
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-green-600 text-white hover:bg-green-700'
              }`}
            >
              {isDiscovering ? 'Running Discovery...' : 'Run Discovery'}
            </button>
            
            {isDiscovering && (
              <div className="flex items-center text-gray-600">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-600 mr-2"></div>
                Processing for up to 5 minutes...
              </div>
            )}
          </div>

          {discoveryStatus && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-blue-800">{discoveryStatus}</p>
            </div>
          )}
        </div>

        {/* Analytics Dashboard */}
        {analytics && (
          <div className="mb-8 grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="font-semibold text-gray-500 text-sm uppercase tracking-wide">Total Artists</h3>
              <p className="text-3xl font-bold text-gray-900 mt-2">{analytics.total_artists || 0}</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="font-semibold text-gray-500 text-sm uppercase tracking-wide">High Value</h3>
              <p className="text-3xl font-bold text-green-600 mt-2">{analytics.high_value_artists || 0}</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="font-semibold text-gray-500 text-sm uppercase tracking-wide">YouTube Quota</h3>
              <p className="text-lg font-bold text-orange-600 mt-2">
                {analytics.api_usage?.youtube?.requests_made || 0} / {analytics.api_usage?.youtube?.quota_limit || 10000}
              </p>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div 
                  className="bg-orange-600 h-2 rounded-full" 
                  style={{width: `${((analytics.api_usage?.youtube?.requests_made || 0) / (analytics.api_usage?.youtube?.quota_limit || 10000)) * 100}%`}}
                ></div>
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="font-semibold text-gray-500 text-sm uppercase tracking-wide">Recent Discoveries</h3>
              <p className="text-3xl font-bold text-blue-600 mt-2">{analytics.recent_discoveries?.length || 0}</p>
            </div>
          </div>
        )}

        {/* Discovery Sessions */}
        <div className="mb-8 bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Discovery Sessions</h2>
          </div>
          <div className="p-6">
            {sessions.length === 0 ? (
              <div className="text-gray-500 text-center py-4">No discovery sessions yet</div>
            ) : (
              <div className="space-y-3">
                {sessions.slice(0, 5).map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <div className="text-sm font-mono text-gray-600">{session.id}</div>
                      <div className="text-xs text-gray-500">
                        Started: {new Date(session.started_at).toLocaleString()}
                        {session.completed_at && (
                          <> • Completed: {new Date(session.completed_at).toLocaleString()}</>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-sm">
                        <span className="font-medium">{session.artists_discovered || 0}</span> artists
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium ${
                        session.status === 'completed' ? 'bg-green-100 text-green-800' :
                        session.status === 'running' ? 'bg-blue-100 text-blue-800' :
                        session.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {session.status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Enhanced Live Activity Stream */}
        <div className="mb-8 bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">🚀 Live Discovery Stream</h2>
              <div className="flex items-center space-x-4">
                <div className={`flex items-center space-x-2 ${wsConnected ? 'text-green-600' : 'text-red-600'}`}>
                  <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                  <span className="text-sm font-medium">
                    {wsConnected ? 'Live' : 'Disconnected'}
                  </span>
                </div>
                <button
                  onClick={() => setLogs([])}
                  className="text-sm px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  Clear Logs
                </button>
              </div>
            </div>
          </div>
          <div className="p-6">
            {/* Progress indicator when discovering */}
            {isDiscovering && (
              <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center space-x-3">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-blue-900">Discovery in Progress</div>
                    <div className="text-xs text-blue-700 mt-1">{discoveryStatus}</div>
                  </div>
                </div>
              </div>
            )}
            
            <div className="bg-gray-900 text-green-400 font-mono text-sm p-4 rounded-lg h-80 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-gray-500">
                    <div className="text-2xl mb-2">📡</div>
                    <div>Waiting for activity...</div>
                    <div className="text-xs mt-2">Real-time discovery logs will appear here</div>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  {logs.map((log, index) => (
                    <div 
                      key={index} 
                      className={`transition-colors ${
                        log.includes('❌') || log.includes('💥') ? 'text-red-400' :
                        log.includes('✅') || log.includes('🎉') ? 'text-green-400' :
                        log.includes('⚠️') ? 'text-yellow-400' :
                        log.includes('🔍') || log.includes('🎤') ? 'text-cyan-400' :
                        log.includes('📊') || log.includes('📹') ? 'text-purple-400' :
                        'text-gray-300'
                      }`}
                    >
                      {log}
                    </div>
                  ))}
                </div>
              )}
              {/* Auto-scroll anchor */}
              <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
            </div>
          </div>
        </div>

        {/* Artists List */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-2xl font-semibold">Discovered Artists ({artists.length})</h2>
          </div>
          
          <div className="p-6">
            {artists.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                No artists discovered yet. Try starting a discovery session!
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {artists.map((artist) => (
                  <div key={artist.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 className="font-semibold text-lg mb-2">{artist.name}</h3>
                    
                    {artist.genres.length > 0 && (
                      <div className="mb-2">
                        <span className="text-sm text-gray-500">Genres: </span>
                        {artist.genres.slice(0, 3).map((genre, index) => (
                          <span key={index} className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded mr-1">
                            {genre}
                          </span>
                        ))}
                      </div>
                    )}
                    
                    <div className="text-sm text-gray-600 space-y-1">
                      {artist.youtube_channel_name && (
                        <div>📺 {artist.youtube_channel_name}</div>
                      )}
                      {artist.location && (
                        <div>📍 {artist.location}</div>
                      )}
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-xs text-gray-500">
                          Score: {(artist.enrichment_score * 100).toFixed(0)}%
                        </span>
                        <span className={`text-xs px-2 py-1 rounded ${
                          artist.status === 'discovered' ? 'bg-green-100 text-green-800' :
                          artist.status === 'enriched' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {artist.status}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App; 