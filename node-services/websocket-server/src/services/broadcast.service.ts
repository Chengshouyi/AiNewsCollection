import { Injectable } from '@nestjs/common';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

@Injectable()
export class BroadcastService {
  constructor(
    private readonly connectionPool: ConnectionPoolService,
    private readonly logger: LoggerService
  ) {}

  async broadcastToRoom(room: string, event: string, data: any) {
    const connections = this.connectionPool.getRoomConnections(room);
    for (const socketId of connections) {
      const socket = this.connectionPool.getConnection(socketId);
      if (socket) {
        socket.emit(event, data);
      }
    }
  }

  async broadcastToAll(event: string, data: any) {
    const connections = this.connectionPool.getAllConnections();
    for (const socket of connections) {
      socket.emit(event, data);
    }
  }
}
