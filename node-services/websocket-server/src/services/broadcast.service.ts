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
        try {
          socket.emit(event, data);
        } catch (error) {
          this.logger.error(
            `廣播到房間 ${room} 的 socket ${socketId} 失敗`,
            error.stack,
            'BroadcastService'
          );
        }
      }
    }
  }

  async broadcastToAll(event: string, data: any) {
    const connections = this.connectionPool.getAllConnections();
    for (const socket of connections) {
      try {
        socket.emit(event, data);
      } catch (error) {
        this.logger.error(
          `廣播到所有連接的 socket ${socket.id} 失敗`,
          error.stack,
          'BroadcastService'
        );
      }
    }
  }
}
