import { Injectable, Logger } from '@nestjs/common';
import { BaseMessage, ChatMessage, TaskMessage } from '../interfaces/message.interface';
import { LoggerService } from '@app/logger';

@Injectable()
export class MessageQueueService {
  private readonly messageQueue = new Map<string, BaseMessage[]>();
  private readonly messageHistory = new Map<string, BaseMessage[]>();
  private readonly maxHistorySize = 100;

  constructor(private readonly logger: LoggerService) {}

  // 儲存訊息到佇列
  async queueMessage(room: string, message: BaseMessage): Promise<void> {
    if (!this.messageQueue.has(room)) {
      this.messageQueue.set(room, []);
    }
    const roomMessages = this.messageQueue.get(room)!;
    roomMessages.push(message);
    this.logger.log(`Message queued for room ${room}: ${message.id}`, MessageQueueService.name);
  }

  // 從佇列中獲取訊息
  async getQueuedMessages(room: string): Promise<BaseMessage[]> {
    const messages = this.messageQueue.get(room) || [];
    this.messageQueue.delete(room);
    this.logger.log(`getQueuedMessages: ${room} ${messages.length}`, MessageQueueService.name);
    return messages;
  }

  // 儲存訊息到歷史記錄
  async saveToHistory(room: string, message: BaseMessage): Promise<void> {
    if (!this.messageHistory.has(room)) {
      this.messageHistory.set(room, []);
    }
    const history = this.messageHistory.get(room)!;
    this.logger.log(`saveToHistory: ${room} ${message.id}`, MessageQueueService.name);
    history.push(message);
    
    // 限制歷史記錄大小
    if (history.length > this.maxHistorySize) {
      history.shift();
    }
  }

  // 獲取歷史訊息
  async getMessageHistory(room: string, limit: number = 50): Promise<BaseMessage[]> {
    const history = this.messageHistory.get(room) || [];
    this.logger.log(`getMessageHistory: ${room} ${history.length}`, MessageQueueService.name);
    return history.slice(-limit);
  }

  // 清除特定房間的歷史記錄
  async clearHistory(room: string): Promise<void> {
    this.messageHistory.delete(room);
    this.logger.log(`History cleared for room ${room}`, MessageQueueService.name);
  }
} 