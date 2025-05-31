export interface BaseMessage {
  id: string;
  type: string;
  timestamp: Date;
  sender: string;
}

export interface ChatMessage extends BaseMessage {
  type: 'chat';
  room: string;
  content: string;
  metadata?: Record<string, any>;
}

export interface TaskMessage extends BaseMessage {
  type: 'task';
  taskId: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
}

export interface SystemMessage extends BaseMessage {
  type: 'system';
  level: 'info' | 'warning' | 'error';
  code: string;
  message: string;
}

export interface AckMessage {
  messageId: string;
  status: 'received' | 'processed' | 'failed';
  timestamp: Date;
  error?: string;
}
