import { Injectable, Logger } from '@nestjs/common';
import { ApiGatewayWebSocket } from './websocket.gateway';

@Injectable()
export class WebSocketService {
  private readonly logger = new Logger(WebSocketService.name);

  constructor(private readonly gateway: ApiGatewayWebSocket) {}

  // 處理錯誤並記錄日誌
  private handleError(error: Error, context: string) {
    this.logger.error(`Error in ${context}: ${error.message}`, error.stack);
    return {
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }

  // 廣播訊息給所有客戶端
  async broadcastMessage(event: string, data: any) {
    try {
      this.gateway.broadcastMessage(event, data);
      this.logger.log(`Broadcast message: ${event}`);
      return {
        success: true,
        event,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return this.handleError(error, 'broadcastMessage');
    }
  }

  // 發送訊息給特定客戶端
  async sendToClient(clientId: string, event: string, data: any) {
    try {
      this.gateway.sendToClient(clientId, event, data);
      this.logger.log(`Sent message to client ${clientId}: ${event}`);
      return {
        success: true,
        clientId,
        event,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return this.handleError(error, 'sendToClient');
    }
  }

  // 發送訊息給特定房間
  async sendToRoom(room: string, event: string, data: any) {
    try {
      this.gateway.sendToRoom(room, event, data);
      this.logger.log(`Sent message to room ${room}: ${event}`);
      return {
        success: true,
        room,
        event,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return this.handleError(error, 'sendToRoom');
    }
  }

  // 獲取連接統計資訊
  getConnectionStats() {
    try {
      const stats = {
        connectedClients: this.gateway.getConnectedClientsCount(),
        timestamp: new Date().toISOString()
      };
      this.logger.log(`Connection stats: ${JSON.stringify(stats)}`);
      return stats;
    } catch (error) {
      return this.handleError(error, 'getConnectionStats');
    }
  }

  // 獲取客戶端所在的房間
  getClientRooms(clientId: string) {
    try {
      const rooms = this.gateway.getClientRooms(clientId);
      this.logger.log(`Client ${clientId} rooms: ${rooms.join(', ')}`);
      return {
        success: true,
        clientId,
        rooms,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return this.handleError(error, 'getClientRooms');
    }
  }
}
