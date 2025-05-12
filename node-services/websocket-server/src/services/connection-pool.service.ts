import { Injectable } from '@nestjs/common';
import { Socket } from 'socket.io';
import { LoggerService } from '@app/logger';

@Injectable()
export class ConnectionPoolService {
  constructor(private readonly logger: LoggerService) {}

  private readonly connections = new Map<string, Socket>();
  private readonly roomConnections = new Map<string, Set<string>>();

  addConnection(socket: Socket) {
    this.connections.set(socket.id, socket);
    this.logger.log(`新增連接: ${socket.id}`);
  }

  removeConnection(socketId: string) {
    this.connections.delete(socketId);
    this.logger.log(`移除連接: ${socketId}`);
  }

  getConnection(socketId: string): Socket | undefined {
    this.logger.log(`獲取連接: ${socketId}`);
    return this.connections.get(socketId);
  }

  addToRoom(socketId: string, room: string) {
    this.logger.log(`添加到房間: ${socketId} -> ${room}`);
    const socket = this.connections.get(socketId);
    if (!socket) {
      this.logger.error(`找不到連接: ${socketId}`);
      return;
    }

    if (!this.roomConnections.has(room)) {
      this.logger.log(`創建新房間: ${room}`);
      this.roomConnections.set(room, new Set());
    }
    this.roomConnections.get(room)?.add(socketId);
    socket.join(room);
    this.logger.log(`添加到房間: ${socketId} -> ${room}`);
  }

  removeFromRoom(socketId: string, room: string) {
    const socket = this.connections.get(socketId);
    if (socket) {
      socket.leave(room);
    }
    this.roomConnections.get(room)?.delete(socketId);
    this.logger.log(`從房間移除: ${socketId} -> ${room}`);
  }

  getRoomConnections(room: string): Set<string> {
    this.logger.log(`獲取房間連接: ${room}`);
    return this.roomConnections.get(room) || new Set();
  }

  getAllConnections(): Socket[] {
    this.logger.log(`獲取所有連接`);
    return Array.from(this.connections.values());
  }
}
