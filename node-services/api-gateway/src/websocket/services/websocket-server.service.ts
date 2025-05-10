import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { WebSocketService } from '../websocket.service';
import { WebSocketMessage, WebSocketResponse } from '../interfaces/websocket-message.interface';
import { io, Socket } from 'socket.io-client';

@Injectable()
export class WebSocketServerService implements OnModuleInit {
  private readonly logger = new Logger(WebSocketServerService.name);
  private socket: Socket;
  private readonly maxRetries = 3;
  private readonly retryDelay = 1000; // 1 second
  private isConnected = false;
  private messageQueue: WebSocketMessage[] = [];

  constructor(
    private readonly configService: ConfigService,
    private readonly webSocketService: WebSocketService,
  ) {}

  async onModuleInit() {
    await this.connect();
  }

  private async connect() {
    const wsServerUrl = this.configService.get<string>('WEBSOCKET_SERVER_URL');
    if (!wsServerUrl) {
      this.logger.error('WebSocket server URL not configured');
      return;
    }

    this.socket = io(wsServerUrl, {
      reconnection: true,
      reconnectionAttempts: this.maxRetries,
      reconnectionDelay: this.retryDelay,
    });

    this.setupEventListeners();
  }

  private setupEventListeners() {
    this.socket.on('connect', () => {
      this.isConnected = true;
      this.logger.log('Connected to WebSocket server');
      this.processMessageQueue();
    });

    this.socket.on('disconnect', () => {
      this.isConnected = false;
      this.logger.warn('Disconnected from WebSocket server');
    });

    this.socket.on('error', (error) => {
      this.logger.error('WebSocket server error:', error);
    });

    // 監聽來自 WebSocket server 的訊息
    this.socket.on('message', async (message: WebSocketMessage) => {
      try {
        await this.handleIncomingMessage(message);
      } catch (error) {
        this.logger.error('Error handling incoming message:', error);
      }
    });
  }

  private async handleIncomingMessage(message: WebSocketMessage) {
    const startTime = Date.now();
    try {
      // 轉發訊息給客戶端
      if (message.clientId) {
        await this.webSocketService.sendToClient(
          message.clientId,
          message.event,
          message.data
        );
      } else {
        await this.webSocketService.broadcastMessage(
          message.event,
          message.data
        );
      }

      // 發送確認訊息回 WebSocket server
      const response: WebSocketResponse = {
        success: true,
        timestamp: new Date().toISOString(),
        metadata: {
          processingTime: Date.now() - startTime,
        },
      };
      this.socket.emit('message_ack', response);
    } catch (error) {
      this.logger.error('Error processing message:', error);
      const response: WebSocketResponse = {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString(),
      };
      this.socket.emit('message_error', response);
    }
  }

  async sendMessage(message: WebSocketMessage): Promise<WebSocketResponse> {
    if (!this.isConnected) {
      this.messageQueue.push(message);
      return {
        success: false,
        error: 'Not connected to WebSocket server',
        timestamp: new Date().toISOString(),
      };
    }

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: 'Message timeout',
          timestamp: new Date().toISOString(),
        });
      }, 5000);

      this.socket.emit('message', message, (response: WebSocketResponse) => {
        clearTimeout(timeout);
        resolve(response);
      });
    });
  }

  private async processMessageQueue() {
    if (!this.isConnected || this.messageQueue.length === 0) return;

    const message = this.messageQueue.shift();
    if (!message) return;

    try {
      await this.sendMessage(message);
    } catch (error) {
      this.logger.error('Error processing queued message:', error);
      const currentRetryCount = message.metadata?.retryCount || 0;
      
      if (currentRetryCount < this.maxRetries) {
        const updatedMessage: WebSocketMessage = {
          ...message,
          metadata: {
            ...message.metadata,
            retryCount: currentRetryCount + 1,
          },
        };
        this.messageQueue.push(updatedMessage);
      }
    }

    // 繼續處理佇列中的其他訊息
    if (this.messageQueue.length > 0) {
      setTimeout(() => this.processMessageQueue(), this.retryDelay);
    }
  }

  async disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
} 