// frontend/src/App.tsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from '@/components/theme-provider';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import { DiscoveryDashboard } from '@/pages/DiscoveryDashboard';
import { ArtistProfile } from '@/pages/ArtistProfile';
import { DiscoveryFlow } from '@/pages/DiscoveryFlow';
import { Analytics } from '@/pages/Analytics';
import { Navigation } from '@/components/Navigation';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="music-discovery-theme">
        <WebSocketProvider>
          <Router>
            <div className="min-h-screen bg-background">
              <Navigation />
              <main className="container mx-auto px-4 py-8">
                <Routes>
                  <Route path="/" element={<DiscoveryDashboard />} />
                  <Route path="/discovery" element={<DiscoveryFlow />} />
                  <Route path="/artist/:id" element={<ArtistProfile />} />
                  <Route path="/analytics" element={<Analytics />} />
                </Routes>
              </main>
              <Toaster position="bottom-right" />
            </div>
          </Router>
        </WebSocketProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;

// frontend/src/contexts/WebSocketContext.tsx
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import toast from 'react-hot-toast';

interface WebSocketContextType {
  isConnected: boolean;
  lastMessage: any;
  sendMessage: (message: any) => void;
  subscribe: (eventType: string, callback: (data: any) => void) => void;
  unsubscribe: (eventType: string, callback: (data: any) => void) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [subscribers, setSubscribers] = useState<Map<string, Set<Function>>>(new Map());

  const connectWebSocket = useCallback(() => {
    const clientId = `client-${Date.now()}`;
    const ws = new WebSocket(`${import.meta.env.VITE_WS_URL}/ws/${clientId}`);

    ws.onopen = () => {
      setIsConnected(true);
      toast.success('Connected to real-time updates');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
        
        // Notify subscribers
        const callbacks = subscribers.get(data.type);
        if (callbacks) {
          callbacks.forEach(callback => callback(data));
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      toast.error('Disconnected from real-time updates');
      // Attempt to reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setSocket(ws);
  }, [subscribers]);

  useEffect(() => {
    connectWebSocket();

    return () => {
      socket?.close();
    };
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }, [socket]);

  const subscribe = useCallback((eventType: string, callback: (data: any) => void) => {
    setSubscribers(prev => {
      const newSubscribers = new Map(prev);
      if (!newSubscribers.has(eventType)) {
        newSubscribers.set(eventType, new Set());
      }
      newSubscribers.get(eventType)!.add(callback);
      return newSubscribers;
    });
  }, []);

  const unsubscribe = useCallback((eventType: string, callback: (data: any) => void) => {
    setSubscribers(prev => {
      const newSubscribers = new Map(prev);
      const callbacks = newSubscribers.get(eventType);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          newSubscribers.delete(eventType);
        }
      }
      return newSubscribers;
    });
  }, []);

  return (
    <WebSocketContext.Provider 
      value={{ 
        isConnected, 
        lastMessage, 
        sendMessage,
        subscribe,
        unsubscribe
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

// frontend/src/pages/DiscoveryDashboard.tsx
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { ArtistCard } from '@/components/ArtistCard';
import { api } from '@/lib/api';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Search, TrendingUp, Users, Music } from 'lucide-react';
import toast from 'react-hot-toast';

export const DiscoveryDashboard: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('official music video');
  const [isDiscovering, setIsDiscovering] = useState(false);
  const { subscribe, unsubscribe } = useWebSocket();

  const { data: artists, refetch } = useQuery({
    queryKey: ['artists'],
    queryFn: () => api.getArtists({ limit: 20 }),
  });

  const { data: analytics } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.getAnalytics(),
  });

  const startDiscovery = async () => {
    try {
      setIsDiscovering(true);
      const response = await api.startDiscovery({
        search_query: searchQuery,
        max_results: 50,
      });
      
      toast.success(`Discovery started! Session ID: ${response.session_id}`);
      
      // Subscribe to discovery events
      const handleDiscoveryComplete = (data: any) => {
        if (data.type === 'discovery_completed') {
          toast.success('Discovery completed!');
          refetch();
          setIsDiscovering(false);
        }
      };
      
      subscribe('discovery_completed', handleDiscoveryComplete);
      
      // Cleanup
      return () => {
        unsubscribe('discovery_completed', handleDiscoveryComplete);
      };
    } catch (error) {
      toast.error('Failed to start discovery');
      setIsDiscovering(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Music Discovery Dashboard</h1>
          <p className="text-muted-foreground">
            Discover emerging artists with AI-powered enrichment
          </p>
        </div>
        <Button
          onClick={() => window.location.href = '/discovery'}
          variant="outline"
        >
          Visual Discovery Flow
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Artists</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics?.total_artists || 0}</div>
            <p className="text-xs text-muted-foreground">
              Discovered artists in database
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High Value</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics?.high_value_artists || 0}</div>
            <p className="text-xs text-muted-foreground">
              Artists with score ≥ 0.7
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">YouTube Quota</CardTitle>
            <Music className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analytics?.api_usage?.youtube?.requests_made || 0} / {analytics?.api_usage?.youtube?.quota_limit || 10000}
            </div>
            <Progress 
              value={(analytics?.api_usage?.youtube?.requests_made || 0) / (analytics?.api_usage?.youtube?.quota_limit || 10000) * 100} 
              className="mt-2"
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Discovery Status</CardTitle>
            <Search className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isDiscovering ? 'Running' : 'Idle'}
            </div>
            <p className="text-xs text-muted-foreground">
              Current discovery status
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Discovery Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Start New Discovery</CardTitle>
          <CardDescription>
            Search YouTube for emerging artists and enrich their profiles
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Input
            placeholder="Search query (e.g., 'official music video')"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1"
          />
          <Button onClick={startDiscovery} disabled={isDiscovering}>
            {isDiscovering ? 'Discovering...' : 'Start Discovery'}
          </Button>
        </CardContent>
      </Card>

      {/* Artists */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Artists</TabsTrigger>
          <TabsTrigger value="high-value">High Value</TabsTrigger>
          <TabsTrigger value="recent">Recent</TabsTrigger>
        </TabsList>
        <TabsContent value="all" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {artists?.map((artist) => (
              <ArtistCard key={artist.id} artist={artist} />
            ))}
          </div>
        </TabsContent>
        <TabsContent value="high-value">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {artists?.filter(a => a.enrichment_score >= 0.7).map((artist) => (
              <ArtistCard key={artist.id} artist={artist} />
            ))}
          </div>
        </TabsContent>
        <TabsContent value="recent">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {analytics?.recent_discoveries?.map((artist) => (
              <ArtistCard key={artist.id} artist={artist} />
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};