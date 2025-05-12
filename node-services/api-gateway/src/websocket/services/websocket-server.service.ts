import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { WebSocketService } from '../websocket.service';
import { WebSocketMessage, WebSocketResponse } from '../interfaces/websocket-message.interface';
import { io, Socket } from 'socket.io-client';
import { LoggerService } from '@app/logger';
@Injectable()
export class WebSocketServerService implements OnModuleInit {
  private socket: Socket;
  private readonly maxRetries = 3;
  private readonly retryDelay = 1000; // 1 second
  private isConnected = false;
  private messageQueue: WebSocketMessage[] = [];

  constructor(
    private readonly configService: ConfigService,
    private readonly webSocketService: WebSocketService,
    private readonly logger: LoggerService,
  ) {}

  async onModuleInit() {
    await this.connect();
  }

  private async connect() {
    const wsServerUrl = this.configService.get<string>('WEBSOCKET_SERVER_URL');
    if (!wsServerUrl) {
      this.logger.error('WebSocket server URL not configured', WebSocketServerService.name);
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
    if (!this.socket) {
      this.logger.error('Socket not initialized', WebSocketServerService.name);
      return;
    }
    this.socket.on('connect', () => {
      this.isConnected = true;
      this.logger.log('Connected to WebSocket server', WebSocketServerService.name);
      this.processMessageQueue();
    });

    this.socket.on('disconnect', () => {
      this.isConnected = false;
      this.logger.warn('Disconnected from WebSocket server', WebSocketServerService.name);
    });

    this.socket.on('error', (error) => {
      this.logger.error('WebSocket server error:', error, WebSocketServerService.name);
    });

    // 監聽來自 WebSocket server 的訊息
    this.socket.on('message', async (message: WebSocketMessage) => {
      try {
        await this.handleIncomingMessage(message);
      } catch (error) {
        this.logger.error('Error handling incoming message:', error, WebSocketServerService.name);
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
        this.logger.log(`sendToClient: ${message.clientId} ${message.event} ${message.data}`, WebSocketServerService.name);
      } else {
        await this.webSocketService.broadcastMessage(
          message.event,
          message.data
        );
        this.logger.log(`broadcastMessage: ${message.event} ${message.data}`, WebSocketServerService.name);

      // 發送確認訊息回 WebSocket server
      const response: WebSocketResponse = {
        success: true,
        timestamp: new Date().toISOString(),
        metadata: {
          processingTime: Date.now() - startTime,
        },
      };
      this.socket.emit('message_ack', response);
      this.logger.log(`message_ack: ${response}`, WebSocketServerService.name);
      }
    } catch (error) {
      this.logger.error('Error processing message:', error, WebSocketServerService.name);
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
      this.logger.error(`sendMessage error: ${message}`, WebSocketServerService.name);
      return {
        success: false,
        error: 'Not connected to WebSocket server',
        timestamp: new Date().toISOString(),
      };
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: 'Message timeout',
          timestamp: new Date().toISOString(),
        });
      }, 5000);

      try {
        this.socket.emit('message', message, (response: WebSocketResponse) => {
          clearTimeout(timeout);
          resolve(response);
        });
      } catch (error) {
        clearTimeout(timeout);
        reject(error);
      }
    });
  }

  private async processMessageQueue() {
    if (!this.isConnected || this.messageQueue.length === 0) return;

    const message = this.messageQueue.shift();
    if (!message) return;

    try {
      await this.sendMessage(message);
    } catch (error) {
      this.logger.error('Error processing queued message:', error, WebSocketServerService.name);
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
        this.logger.log(`processMessageQueue: ${updatedMessage}`, WebSocketServerService.name);
      }
    }

    // 繼續處理佇列中的其他訊息
    if (this.messageQueue.length > 0) {
      setTimeout(() => this.processMessageQueue(), this.retryDelay);
      this.logger.log(`processMessageQueue: ${this.messageQueue.length}`, WebSocketServerService.name);
    }
  }

  async disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.logger.log('Disconnected from WebSocket server', WebSocketServerService.name);
    }
  }
} 