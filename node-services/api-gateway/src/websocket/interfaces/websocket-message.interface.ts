export interface WebSocketMessage {
  event: string;
  data: any;
  timestamp: string;
  clientId?: string;
  metadata?: {
    retryCount?: number;
    source?: string;
    target?: string;
  };
}

export interface WebSocketResponse {
  success: boolean;
  error?: string;
  data?: any;
  timestamp: string;
  metadata?: {
    retryCount?: number;
    processingTime?: number;
  };
} 