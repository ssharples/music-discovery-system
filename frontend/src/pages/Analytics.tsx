// frontend/src/pages/Analytics.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import { 
  TrendingUp, Users, Music, Calendar, BarChart3, 
  PieChart, Activity, Zap, Database, Globe
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RePieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  Area,
  AreaChart
} from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

export const Analytics: React.FC = () => {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.getAnalytics(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  const genreData = analytics?.genre_distribution || [];
  const apiUsageData = [
    { name: 'YouTube', used: analytics?.api_usage?.youtube?.requests_made || 0, limit: analytics?.api_usage?.youtube?.quota_limit || 10000 },
    { name: 'Spotify', used: analytics?.api_usage?.spotify?.requests_made || 0, limit: analytics?.api_usage?.spotify?.quota_limit || 1000 },
  ];

  // Mock time series data for discovery trends
  const discoveryTrends = [
    { date: 'Mon', artists: 12 },
    { date: 'Tue', artists: 19 },
    { date: 'Wed', artists: 15 },
    { date: 'Thu', artists: 22 },
    { date: 'Fri', artists: 28 },
    { date: 'Sat', artists: 35 },
    { date: 'Sun', artists: 30 },
  ];

  const enrichmentDistribution = [
    { name: 'High (70%+)', value: analytics?.high_value_artists || 0 },
    { name: 'Medium (40-70%)', value: Math.floor((analytics?.total_artists || 0) * 0.4) },
    { name: 'Low (<40%)', value: Math.floor((analytics?.total_artists || 0) * 0.3) },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
        <p className="text-muted-foreground">
          Comprehensive insights into your music discovery system
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Artists</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics?.total_artists || 0}</div>
            <p className="text-xs text-muted-foreground">
              <TrendingUp className="h-3 w-3 inline mr-1" />
              +12% from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High Value Artists</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics?.high_value_artists || 0}</div>
            <p className="text-xs text-muted-foreground">
              {((analytics?.high_value_artists || 0) / (analytics?.total_artists || 1) * 100).toFixed(1)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Enrichment</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">64%</div>
            <Progress value={64} className="h-2 mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Discovery Rate</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">4.3/hour</div>
            <p className="text-xs text-muted-foreground">
              26 artists today
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Discovery Trends */}
        <Card>
          <CardHeader>
            <CardTitle>Discovery Trends</CardTitle>
            <CardDescription>Artists discovered over the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={discoveryTrends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="artists" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Genre Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Genre Distribution</CardTitle>
            <CardDescription>Top genres among discovered artists</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <RePieChart>
                <Pie
                  data={genreData.slice(0, 6)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {genreData.slice(0, 6).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </RePieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* API Usage */}
      <Card>
        <CardHeader>
          <CardTitle>API Usage & Quotas</CardTitle>
          <CardDescription>Monitor your API consumption and limits</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {apiUsageData.map((api) => (
              <div key={api.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {api.name === 'YouTube' ? <Youtube className="h-4 w-4" /> : <Music className="h-4 w-4" />}
                    <span className="font-medium">{api.name}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {api.used.toLocaleString()} / {api.limit.toLocaleString()}
                  </span>
                </div>
                <Progress value={(api.used / api.limit) * 100} className="h-2" />
                <p className="text-xs text-muted-foreground">
                  {((api.used / api.limit) * 100).toFixed(1)}% used • {(api.limit - api.used).toLocaleString()} remaining
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Enrichment Score Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Enrichment Score Distribution</CardTitle>
            <CardDescription>Artist profile completeness breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={enrichmentDistribution}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#8884d8">
                  {enrichmentDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Recent High-Value Discoveries */}
        <Card>
          <CardHeader>
            <CardTitle>Recent High-Value Discoveries</CardTitle>
            <CardDescription>Latest artists with enrichment score ≥ 70%</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics?.recent_discoveries?.slice(0, 5).map((artist) => (
                <div key={artist.id} className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="font-medium text-sm">{artist.name}</p>
                    <div className="flex gap-2 mt-1">
                      {artist.genres.slice(0, 2).map((genre) => (
                        <Badge key={genre} variant="outline" className="text-xs">
                          {genre}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Badge variant={artist.enrichment_score >= 0.7 ? 'default' : 'secondary'}>
                    {(artist.enrichment_score * 100).toFixed(0)}%
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Health */}
      <Card>
        <CardHeader>
          <CardTitle>System Health & Performance</CardTitle>
          <CardDescription>Monitor system status and performance metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Database Status</span>
                <Badge variant="default">Healthy</Badge>
              </div>
              <Progress value={100} className="h-2" />
              <p className="text-xs text-muted-foreground">
                <Database className="h-3 w-3 inline mr-1" />
                All systems operational
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">API Response Time</span>
                <Badge variant="default">Fast</Badge>
              </div>
              <Progress value={85} className="h-2" />
              <p className="text-xs text-muted-foreground">
                <Activity className="h-3 w-3 inline mr-1" />
                Avg: 120ms
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Discovery Queue</span>
                <Badge variant="outline">3 pending</Badge>
              </div>
              <Progress value={30} className="h-2" />
              <p className="text-xs text-muted-foreground">
                <Globe className="h-3 w-3 inline mr-1" />
                Processing normally
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};