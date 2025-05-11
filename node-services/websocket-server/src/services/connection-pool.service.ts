@Injectable()
export class ConnectionPoolService {
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
    return this.connections.get(socketId);
  }

  addToRoom(socketId: string, room: string) {
    if (!this.roomConnections.has(room)) {
      this.roomConnections.set(room, new Set());
    }
    this.roomConnections.get(room).add(socketId);
  }

  removeFromRoom(socketId: string, room: string) {
    this.roomConnections.get(room)?.delete(socketId);
  }
}
