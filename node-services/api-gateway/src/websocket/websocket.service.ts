import { Injectable, Logger } from '@nestjs/common';
import { ApiGatewayWebSocket } from './websocket.gateway';
import { LoggerService } from '@app/logger';

interface BroadcastResponse {
  success: boolean;
  event?: string;
  error?: string;
  timestamp: string;
}

interface SendToClientResponse {
  success: boolean;
  clientId?: string;
  event?: string;
  error?: string;
  timestamp: string;
}

interface ConnectionStatsResponse {
  success: boolean;
  connectedClients?: number;
  error?: string;
  timestamp: string;
}

@Injectable()
export class WebSocketService {

  constructor(private readonly gateway: ApiGatewayWebSocket, private readonly logger: LoggerService) {}

  // 處理錯誤並記錄日誌
  private handleError(error: Error, context: string) {
    this.logger.error(`Error in ${context}: ${error.message}`, WebSocketService.name);
    return {
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }

  // 廣播訊息給所有客戶端
  async broadcastMessage(event: string, data: any): Promise<BroadcastResponse> {
    try {
      this.gateway.broadcastMessage(event, data);
      this.logger.log(`Broadcast message: ${event}`, WebSocketService.name);
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
  async sendToClient(clientId: string, event: string, data: any): Promise<SendToClientResponse> {
    try {
      this.gateway.sendToClient(clientId, event, data);
      this.logger.log(`Sent message to client ${clientId}: ${event}`, WebSocketService.name);
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
      this.logger.log(`Sent message to room ${room}: ${event}`, WebSocketService.name);
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
  getConnectionStats(): ConnectionStatsResponse {
    try {
      const count = this.gateway.getConnectedClientsCount();
      return {
        success: true,
        connectedClients: count,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return this.handleError(error, 'getConnectionStats');
    }
  }

  // 獲取客戶端所在的房間
  getClientRooms(clientId: string) {
    try {
      const rooms = this.gateway.getClientRooms(clientId);
      this.logger.log(`Client ${clientId} rooms: ${rooms.join(', ')}`, WebSocketService.name);
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
