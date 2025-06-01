import { Injectable } from '@nestjs/common';
import { Server, Socket } from 'socket.io';
import { v4 as uuidv4 } from 'uuid';
import {
  BaseMessage,
  SystemMessage,
  AckMessage,
} from './interfaces/message.interface';
import { LoggerService } from '@app/logger';

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
  private io: Server;
  private readonly reconnectAttempts = new Map<string, number>();
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000; // 1秒

  constructor(private readonly logger: LoggerService) {}

  setSocketServer(server: Server) {
    this.io = server;
    this.setupErrorHandling();
  }

  private setupErrorHandling() {
    this.io.on('error', (error) => {
      this.logger.error('Socket.IO server error:', error, AppService.name);
    });

    this.io.on('connection', (socket: Socket) => {
      this.handleConnection(socket);
    });
  }

  private handleConnection(socket: Socket) {
    const clientId = socket.id;
    this.reconnectAttempts.set(clientId, 0);

    socket.on('error', (error) => {
      this.logger.error(`Client ${clientId} error:`, error, AppService.name);
      this.handleClientError(socket, error);
    });

    socket.on('disconnect', (reason) => {
      this.logger.log(
        `Client ${clientId} disconnected: ${reason}`,
        AppService.name,
      );
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
    this.logger.error(`Error for client ${clientId}:`, error, AppService.name);

    // 發送錯誤訊息給客戶端
    this.sendSystemMessage(socket, {
      level: 'error',
      code: 'CLIENT_ERROR',
      message: '發生錯誤，請稍後重試',
    });
  }

  private handleReconnection(socket: Socket) {
    const clientId = socket.id;
    const attempts = this.reconnectAttempts.get(clientId) || 0;

    if (attempts < this.maxReconnectAttempts) {
      const nextAttempt = attempts + 1;
      this.reconnectAttempts.set(clientId, nextAttempt);
      this.logger.log(
        `Scheduling reconnection attempt ${nextAttempt} for client ${clientId} in ${this.reconnectDelay * nextAttempt}ms`,
        AppService.name,
      );

      setTimeout(() => {
        const currentAttempts = this.reconnectAttempts.get(clientId);
        if (currentAttempts !== nextAttempt) {
          this.logger.log(
            `Reconnection attempt ${nextAttempt} for ${clientId} aborted or superseded.`,
            AppService.name,
          );
          return;
        }

        if (socket.connected) {
          this.logger.log(
            `Client ${clientId} reconnected successfully on attempt ${nextAttempt}`,
            AppService.name,
          );
          this.reconnectAttempts.delete(clientId);
        } else {
          this.logger.log(
            `Client ${clientId} still not connected after attempt ${nextAttempt}.`,
            AppService.name,
          );
          if (nextAttempt < this.maxReconnectAttempts) {
            this.handleReconnection(socket);
          } else {
            this.logger.warn(
              `Client ${clientId} exceeded max reconnection attempts after timeout check.`,
              AppService.name,
            );
            this.reconnectAttempts.delete(clientId);
          }
        }
      }, this.reconnectDelay * nextAttempt);
    } else {
      this.logger.warn(
        `Client ${clientId} already exceeded max reconnection attempts before scheduling attempt ${attempts + 1}`,
        AppService.name,
      );
      this.reconnectAttempts.delete(clientId);
    }
  }

  private sendSystemMessage(
    socket: Socket,
    data: Omit<SystemMessage, keyof BaseMessage>,
  ) {
    const message: SystemMessage = {
      id: uuidv4(),
      type: 'system',
      timestamp: new Date(),
      sender: 'system',
      ...data,
    };
    this.logger.log(`sendSystemMessage: ${message.message}`, AppService.name);
    socket.emit('system_message', message);
  }

  getSocketServer(): Server {
    this.logger.log('getSocketServer', AppService.name);
    return this.io;
  }

  // 向特定房間發送訊息
  emitToRoom(room: string, event: string, data: any) {
    if (this.io) {
      this.logger.log(`emitToRoom: ${room} ${event} ${data}`, AppService.name);
      this.io.to(room).emit(event, data);
    }
  }

  // 向所有客戶端發送訊息
  emitToAll(event: string, data: any) {
    if (this.io) {
      this.logger.log(`emitToAll: ${event} ${data}`, AppService.name);
      this.io.emit(event, data);
    }
  }

  // 廣播給房間內除了發送者外的所有人
  emitToRoomExcludingSender(
    room: string,
    event: string,
    data: any,
    senderId: string,
  ) {
    if (this.io) {
      this.logger.log(
        `emitToRoomExcludingSender: ${room} ${event} ${data} ${senderId}`,
        AppService.name,
      );
      this.io.to(room).except(senderId).emit(event, data);
    }
  }

  // 廣播給房間內所有人（包括發送者）
  emitToRoomIncludingSender(room: string, event: string, data: any) {
    if (this.io) {
      this.logger.log(
        `emitToRoomIncludingSender: ${room} ${event} ${data}`,
        AppService.name,
      );
      this.io.to(room).emit(event, data);
    }
  }

  getHello(): string {
    this.logger.log('getHello', AppService.name);
    return 'Hello World!';
  }

  sendMessageToRoom(room: string, message: string, senderId: string): void {
    const payload: MessagePayload = {
      user: senderId,
      room,
      message,
      timestamp: new Date(),
    };
    this.logger.log(
      `sendMessageToRoom: ${room} ${message} ${senderId}`,
      AppService.name,
    );
    this.emitToRoom(room, 'new_message', payload);
  }

  updateTaskProgress(
    taskId: number,
    status: string,
    progress: number,
    message: string,
  ): void {
    const payload: TaskProgressPayload = {
      task_id: taskId,
      status,
      progress,
      message,
      timestamp: new Date(),
    };
    this.logger.log(
      `updateTaskProgress: ${taskId} ${status} ${progress} ${message}`,
      AppService.name,
    );
    this.emitToRoom(`task_${taskId}`, 'task_progress', payload);
  }

  // 發送訊息並等待確認
  async sendMessageWithAck(
    room: string,
    message: BaseMessage,
    timeout: number = 5000,
  ): Promise<boolean> {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.logger.warn(
          `Message ${message as unknown as string} ACK timeout`,
          AppService.name,
        );
        resolve(false);
      }, timeout);

      this.io.to(room).emit('message', message, (ack: AckMessage) => {
        clearTimeout(timer);
        if (ack.status === 'received') {
          this.logger.log(
            `Message ${message as unknown as string} acknowledged`,
            AppService.name,
          );
          resolve(true);
        } else {
          this.logger.error(
            `Message ${message as unknown as string} failed: ${ack.error}`,
            AppService.name,
          );
          resolve(false);
        }
      });
    });
  }

  // 處理訊息確認
  private handleMessageAck(
    socket: Socket,
    messageId: string,
    status: 'received' | 'processed' | 'failed',
    error?: string,
  ) {
    const ack: AckMessage = {
      messageId,
      status,
      timestamp: new Date(),
      error,
    };
    this.logger.log(
      `handleMessageAck: ${messageId} ${status} ${error}`,
      AppService.name,
    );
    socket.emit('message_ack', ack);
  }

  // 廣播訊息（可選擇是否包含發送者）
  broadcastMessage(
    room: string,
    message: BaseMessage,
    includeSender: boolean = false,
  ) {
    if (includeSender) {
      this.logger.log(
        `broadcastMessage: ${room} ${message as unknown as string} ${includeSender}`,
        AppService.name,
      );
      this.emitToRoomIncludingSender(room, 'message', message);
    } else {
      this.logger.log(
        `broadcastMessage: ${room} ${message as unknown as string} ${includeSender}`,
        AppService.name,
      );
      this.emitToRoomExcludingSender(room, 'message', message, message.sender);
    }
  }
}
