export interface ClientState {
  id: string;
  connected: boolean;
  rooms: string[];
  lastActivity: Date;
  metadata?: Record<string, any>;
}

export interface SystemMetrics {
  activeConnections: number;
  messagesPerSecond: number;
  averageLatency: number;
  errorRate: number;
  timestamp: Date;
}

export interface QueueMetrics {
  messagesProcessed: number;
  messagesFailed: number;
  averageProcessingTime: number;
  queueSize: number;
  timestamp: Date;
}

export interface WebSocketMessage {
  type: 'chat' | 'system' | 'task' | 'ack';
  payload: any;
  metadata?: Record<string, any>;
  timestamp: Date;
}

export interface Room {
  id: string;
  name: string;
  members: string[];
  createdAt: Date;
  metadata?: Record<string, any>;
}
