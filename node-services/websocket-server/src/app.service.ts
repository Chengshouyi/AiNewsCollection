import { Injectable, Logger } from '@nestjs/common';
import { Server, Socket } from 'socket.io';
import { v4 as uuidv4 } from 'uuid';
import { BaseMessage, ChatMessage, TaskMessage, SystemMessage, AckMessage } from './interfaces/message.interface';

interface MessagePayload {
  user: string;
  room: string;
  message: string;
  timestamp: Date;
}

interface TaskProgressPayload {
  task_id: number;
  status: string;
  progress: number;
  message: string;
  timestamp: Date;
}

@Injectable()
export class AppService {
  private readonly logger = new Logger(AppService.name);
  private io: Server;
  private readonly reconnectAttempts = new Map<string, number>();
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000; // 1秒

  setSocketServer(server: Server) {
    this.io = server;
    this.setupErrorHandling();
  }

  private setupErrorHandling() {
    this.io.on('error', (error) => {
      this.logger.error('Socket.IO server error:', error);
    });

    this.io.on('connection', (socket: Socket) => {
      this.handleConnection(socket);
    });
  }

  private handleConnection(socket: Socket) {
    const clientId = socket.id;
    this.reconnectAttempts.set(clientId, 0);

    socket.on('error', (error) => {
      this.logger.error(`Client ${clientId} error:`, error);
      this.handleClientError(socket, error);
    });

    socket.on('disconnect', (reason) => {
      this.logger.log(`Client ${clientId} disconnected: ${reason}`);
      if (reason === 'transport close') {
        this.handleReconnection(socket);
      }
    });

    // 心跳檢測
    socket.on('ping', () => {
      socket.emit('pong', { timestamp: new Date() });
    });
  }

  private handleClientError(socket: Socket, error: Error) {
    const clientId = socket.id;
    this.logger.error(`Error for client ${clientId}:`, error);
    
    // 發送錯誤訊息給客戶端
    this.sendSystemMessage(socket, {
      level: 'error',
      code: 'CLIENT_ERROR',
      message: '發生錯誤，請稍後重試'
    });
  }

  private handleReconnection(socket: Socket) {
    const clientId = socket.id;
    const attempts = this.reconnectAttempts.get(clientId) || 0;

    if (attempts < this.maxReconnectAttempts) {
      this.reconnectAttempts.set(clientId, attempts + 1);
      setTimeout(() => {
        if (socket.connected) {
          this.logger.log(`Client ${clientId} reconnected successfully`);
          this.reconnectAttempts.delete(clientId);
        }
      }, this.reconnectDelay * (attempts + 1));
    } else {
      this.logger.warn(`Client ${clientId} exceeded max reconnection attempts`);
      this.reconnectAttempts.delete(clientId);
    }
  }

  private sendSystemMessage(socket: Socket, data: Omit<SystemMessage, keyof BaseMessage>) {
    const message: SystemMessage = {
      id: uuidv4(),
      type: 'system',
      timestamp: new Date(),
      sender: 'system',
      ...data
    };
    socket.emit('system_message', message);
  }

  getSocketServer(): Server {
    return this.io;
  }

  // 向特定房間發送訊息
  emitToRoom(room: string, event: string, data: any) {
    if (this.io) {
      this.io.to(room).emit(event, data);
    }
  }

  // 向所有客戶端發送訊息
  emitToAll(event: string, data: any) {
    if (this.io) {
      this.io.emit(event, data);
    }
  }

  // 廣播給房間內除了發送者外的所有人
  emitToRoomExcludingSender(room: string, event: string, data: any, senderId: string) {
    if (this.io) {
      this.io.to(room).except(senderId).emit(event, data);
    }
  }

  // 廣播給房間內所有人（包括發送者）
  emitToRoomIncludingSender(room: string, event: string, data: any) {
    if (this.io) {
      this.io.to(room).emit(event, data);
    }
  }

  getHello(): string {
    this.logger.log('getHello');
    return 'Hello World!';
  }

  sendMessageToRoom(room: string, message: string, senderId: string): void {
    const payload: MessagePayload = {
      user: senderId,
      room,
      message,
      timestamp: new Date()
    };
    this.emitToRoom(room, 'new_message', payload);
  }

  updateTaskProgress(taskId: number, status: string, progress: number, message: string): void {
    const payload: TaskProgressPayload = {
      task_id: taskId,
      status,
      progress,
      message,
      timestamp: new Date()
    };
    this.emitToRoom(`task_${taskId}`, 'task_progress', payload);
  }

  // 發送訊息並等待確認
  async sendMessageWithAck(room: string, message: BaseMessage, timeout: number = 5000): Promise<boolean> {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.logger.warn(`Message ${message.id} ACK timeout`);
        resolve(false);
      }, timeout);

      this.io.to(room).emit('message', message, (ack: AckMessage) => {
        clearTimeout(timer);
        if (ack.status === 'received') {
          this.logger.log(`Message ${message.id} acknowledged`);
          resolve(true);
        } else {
          this.logger.error(`Message ${message.id} failed: ${ack.error}`);
          resolve(false);
        }
      });
    });
  }

  // 處理訊息確認
  private handleMessageAck(socket: Socket, messageId: string, status: 'received' | 'processed' | 'failed', error?: string) {
    const ack: AckMessage = {
      messageId,
      status,
      timestamp: new Date(),
      error
    };
    socket.emit('message_ack', ack);
  }

  // 廣播訊息（可選擇是否包含發送者）
  async broadcastMessage(room: string, message: BaseMessage, includeSender: boolean = false) {
    if (includeSender) {
      this.emitToRoomIncludingSender(room, 'message', message);
    } else {
      this.emitToRoomExcludingSender(room, 'message', message, message.sender);
    }
  }
}
