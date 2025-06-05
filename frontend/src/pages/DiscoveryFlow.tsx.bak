// frontend/src/pages/DiscoveryFlow.tsx
import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  NodeProps,
  ConnectionMode,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Youtube, Music, Database, Brain, Search } from 'lucide-react';
import toast from 'react-hot-toast';

// Custom node types
const YouTubeNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <Card className="w-64 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Youtube className="h-5 w-5 text-red-500" />
          <CardTitle className="text-sm">YouTube Discovery</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{data.label}</p>
        {data.status && (
          <Badge variant={data.status === 'active' ? 'default' : 'secondary'} className="mt-2">
            {data.status}
          </Badge>
        )}
        {data.progress !== undefined && (
          <Progress value={data.progress} className="mt-2" />
        )}
      </CardContent>
      <Handle type="source" position={Position.Right} />
    </Card>
  );
};

const EnrichmentNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <Card className="w-64 shadow-lg">
      <Handle type="target" position={Position.Left} />
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Search className="h-5 w-5 text-blue-500" />
          <CardTitle className="text-sm">Enrichment</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{data.label}</p>
        <div className="mt-2 space-y-1">
          {data.sources && data.sources.map((source: string, idx: number) => (
            <Badge key={idx} variant="outline" className="text-xs">
              {source}
            </Badge>
          ))}
        </div>
      </CardContent>
      <Handle type="source" position={Position.Right} />
    </Card>
  );
};

const AnalysisNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <Card className="w-64 shadow-lg">
      <Handle type="target" position={Position.Left} />
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-500" />
          <CardTitle className="text-sm">AI Analysis</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{data.label}</p>
        {data.metrics && (
          <div className="mt-2 space-y-1 text-xs">
            <div>Themes: {data.metrics.themes}</div>
            <div>Sentiment: {data.metrics.sentiment}</div>
          </div>
        )}
      </CardContent>
      <Handle type="source" position={Position.Right} />
    </Card>
  );
};

const StorageNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <Card className="w-64 shadow-lg">
      <Handle type="target" position={Position.Left} />
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-green-500" />
          <CardTitle className="text-sm">Storage</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{data.label}</p>
        {data.count !== undefined && (
          <div className="mt-2 text-sm font-medium">
            {data.count} artists stored
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const nodeTypes = {
  youtube: YouTubeNode,
  enrichment: EnrichmentNode,
  analysis: AnalysisNode,
  storage: StorageNode,
};

const initialNodes: Node[] = [
  {
    id: '1',
    type: 'youtube',
    position: { x: 100, y: 100 },
    data: { 
      label: 'Search for new music videos',
      status: 'idle',
      progress: 0
    },
  },
  {
    id: '2',
    type: 'enrichment',
    position: { x: 400, y: 100 },
    data: { 
      label: 'Enrich artist profiles',
      sources: ['Spotify', 'Instagram', 'Firecrawl']
    },
  },
  {
    id: '3',
    type: 'analysis',
    position: { x: 700, y: 100 },
    data: { 
      label: 'Analyze lyrics & content',
      metrics: { themes: 'N/A', sentiment: 'N/A' }
    },
  },
  {
    id: '4',
    type: 'storage',
    position: { x: 1000, y: 100 },
    data: { 
      label: 'Store in Supabase',
      count: 0
    },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3', animated: true },
  { id: 'e3-4', source: '3', target: '4', animated: true },
];

export const DiscoveryFlow: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { subscribe, unsubscribe } = useWebSocket();
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    // Subscribe to WebSocket events
    const handleDiscoveryStarted = (data: any) => {
      setIsRunning(true);
      updateNodeData('1', { status: 'active', progress: 0 });
      toast.success('Discovery started!');
    };

    const handleDiscoveryProgress = (data: any) => {
      // Update progress based on the stage
      if (data.progress.stage === 'youtube_search') {
        updateNodeData('1', { progress: data.progress.percentage });
      } else if (data.progress.stage === 'enrichment') {
        updateNodeData('1', { status: 'completed', progress: 100 });
        updateNodeData('2', { status: 'active' });
      } else if (data.progress.stage === 'analysis') {
        updateNodeData('2', { status: 'completed' });
        updateNodeData('3', { status: 'active' });
      }
    };

    const handleArtistDiscovered = (data: any) => {
      // Update storage count
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === '4') {
            return {
              ...node,
              data: {
                ...node.data,
                count: (node.data.count || 0) + 1,
              },
            };
          }
          return node;
        })
      );
    };

    const handleDiscoveryCompleted = (data: any) => {
      setIsRunning(false);
      updateNodeData('3', { status: 'completed' });
      updateNodeData('4', { status: 'completed' });
      toast.success(`Discovery completed! Found ${data.summary.artists_discovered} artists`);
    };

    subscribe('discovery_started', handleDiscoveryStarted);
    subscribe('discovery_progress', handleDiscoveryProgress);
    subscribe('artist_discovered', handleArtistDiscovered);
    subscribe('discovery_completed', handleDiscoveryCompleted);

    return () => {
      unsubscribe('discovery_started', handleDiscoveryStarted);
      unsubscribe('discovery_progress', handleDiscoveryProgress);
      unsubscribe('artist_discovered', handleArtistDiscovered);
      unsubscribe('discovery_completed', handleDiscoveryCompleted);
    };
  }, [subscribe, unsubscribe]);

  const updateNodeData = (nodeId: string, data: any) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            data: {
              ...node.data,
              ...data,
            },
          };
        }
        return node;
      })
    );
  };

  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const startDiscovery = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/discover`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          search_query: 'official music video',
          max_results: 50,
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        toast.success(`Discovery started! Session: ${data.session_id}`);
      }
    } catch (error) {
      toast.error('Failed to start discovery');
    }
  };

  return (
    <div className="h-screen w-full">
      <div className="absolute top-4 left-4 z-10">
        <Card>
          <CardHeader>
            <CardTitle>Discovery Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <Button
              onClick={startDiscovery}
              disabled={isRunning}
              className="w-full"
            >
              {isRunning ? 'Discovery Running...' : 'Start Discovery'}
            </Button>
          </CardContent>
        </Card>
      </div>
      
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
      >
        <Background variant="dots" gap={12} size={1} />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};