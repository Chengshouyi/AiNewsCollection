import { WebSocketGateway, WebSocketServer, OnGatewayConnection, OnGatewayDisconnect, OnGatewayInit, SubscribeMessage } from '@nestjs/websockets';
import { Server, Socket, Namespace } from 'socket.io';
// import { Logger } from '@nestjs/common'; // Temporarily comment out Logger
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';
@WebSocketGateway({
  cors: {
    origin: '*',
  },
  namespace: 'api-gateway',
})
export class ApiGatewayWebSocket implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect {
  // private readonly logger = new Logger(ApiGatewayWebSocket.name); // Temporarily comment out Logger
  private connectedClients: Map<string, Socket> = new Map();
  private clientRooms: Map<string, Set<string>> = new Map();
  private readonly heartbeatInterval: number;
  private pingIntervalTimers: Map<string, NodeJS.Timeout> = new Map(); // Renamed for clarity
  private heartbeatTimeoutTimers: Map<string, NodeJS.Timeout> = new Map(); // Added to store heartbeat timeouts

  @WebSocketServer()
  server: Namespace;

  constructor(private readonly configService: ConfigService, private readonly logger: LoggerService) {
    this.logger.log('ApiGatewayWebSocket CONSTRUCTOR called', ApiGatewayWebSocket.name);
    this.heartbeatInterval = this.configService.get('WEBSOCKET_HEARTBEAT_INTERVAL', 30000);
    this.logger.log(`Heartbeat interval set to: ${this.heartbeatInterval}`, ApiGatewayWebSocket.name);
  }

  afterInit(server: Namespace) {
    this.logger.log('ApiGatewayWebSocket afterInit called', ApiGatewayWebSocket.name);
    if (server) {
      this.logger.log(`afterInit: server argument name: ${server.name}`, ApiGatewayWebSocket.name);
      this.logger.log(`afterInit: this.server name: ${this.server?.name}`, ApiGatewayWebSocket.name);
    } else {
      this.logger.log('afterInit: server argument is NULL or UNDEFINED', ApiGatewayWebSocket.name);
    }
  }

  handleConnection(client: Socket) {
    const clientId = client.id;
    this.connectedClients.set(clientId, client);
    this.clientRooms.set(clientId, new Set());
    this.logger.log(`Client connected: ${clientId} - handleConnection START, in namespace: ${client.nsp.name}`, ApiGatewayWebSocket.name);
    
    this.logger.log(`Calling setupHeartbeat for ${clientId}`, ApiGatewayWebSocket.name);
    this.setupHeartbeat(client);
    this.logger.log(`Finished setupHeartbeat for ${clientId}`, ApiGatewayWebSocket.name);

    this.logger.log(`Attempting to send 'welcome' message to ${clientId}`, ApiGatewayWebSocket.name);
    client.emit('welcome', {
      message: 'Welcome to API Gateway WebSocket',
      clientId,
      timestamp: new Date().toISOString()
    });
    this.logger.log(`'welcome' message sent to ${clientId}`, ApiGatewayWebSocket.name);
  }

  handleDisconnect(client: Socket) {
    const clientId = client.id;
    this.logger.log(`handleDisconnect for ${clientId} - calling cleanupClient`, ApiGatewayWebSocket.name);
    this.cleanupClient(clientId);
    this.logger.log(`Client disconnected: ${clientId}`, ApiGatewayWebSocket.name);
  }

  @SubscribeMessage('join_room')
  handleJoinRoom(client: Socket, data: { room: string }) {
    const clientId = client.id;
    const { room } = data;
    this.logger.log(`handleJoinRoom called by ${clientId} for room ${room}`, ApiGatewayWebSocket.name);
    try {
      client.join(room);
      const rooms = this.clientRooms.get(clientId) || new Set();
      rooms.add(room);
      this.clientRooms.set(clientId, rooms);

      this.logger.log(`Client ${clientId} joined room: ${room}`, ApiGatewayWebSocket.name);
      client.emit('room_joined', {
        room,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      this.logger.error(`Error joining room for ${clientId}: ${error.message}`, ApiGatewayWebSocket.name);
      client.emit('error', {
        message: 'Failed to join room',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }

  @SubscribeMessage('leave_room')
  handleLeaveRoom(client: Socket, data: { room: string }) {
    const clientId = client.id;
    const { room } = data;
    this.logger.log(`handleLeaveRoom called by ${clientId} for room ${room}`, ApiGatewayWebSocket.name);
    try {
      client.leave(room);
      const rooms = this.clientRooms.get(clientId);
      if (rooms) {
        rooms.delete(room);
      }

      this.logger.log(`Client ${clientId} left room: ${room}`, ApiGatewayWebSocket.name);
      client.emit('room_left', {
        room,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      this.logger.error(`Error leaving room for ${clientId}: ${error.message}`, ApiGatewayWebSocket.name);
      client.emit('error', {
        message: 'Failed to leave room',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }

  @SubscribeMessage('ping')
  handlePing(client: Socket) {
    this.logger.log(`handlePing called by ${client.id}`, ApiGatewayWebSocket.name);
    client.emit('pong', {
      timestamp: new Date().toISOString()
    });
  }

  // 廣播訊息給所有連接的客戶端
  broadcastMessage(event: string, data: any) {
    this.server.emit(event, {
      ...data,
      timestamp: new Date().toISOString()
    });
    this.logger.log(`broadcastMessage: ${event} ${data}`, ApiGatewayWebSocket.name);
  }

  // 發送訊息給特定客戶端
  sendToClient(clientId: string, event: string, data: any) {
    const client = this.connectedClients.get(clientId);
    if (client) {
      client.emit(event, {
        ...data,
        timestamp: new Date().toISOString()
      });
      this.logger.log(`sendToClient: ${clientId} ${event} ${data}`, ApiGatewayWebSocket.name);
    }
  }

  // 發送訊息給特定房間
  sendToRoom(room: string, event: string, data: any) {
    this.server.to(room).emit(event, {
      ...data,
      timestamp: new Date().toISOString()
    });
    this.logger.log(`sendToRoom: ${room} ${event} ${data}`, ApiGatewayWebSocket.name);
  }

  // 獲取當前連接的客戶端數量
  getConnectedClientsCount(): number {
    this.logger.log(`getConnectedClientsCount: ${this.connectedClients.size}`, ApiGatewayWebSocket.name);
    return this.connectedClients.size;
  }

  // 獲取客戶端所在的房間
  getClientRooms(clientId: string): string[] {
    const rooms = this.clientRooms.get(clientId);
    return rooms ? Array.from(rooms) : [];
  }

  private setupHeartbeat(client: Socket) {
    const clientId = client.id;
    this.logger.log(`setupHeartbeat for ${clientId}`, ApiGatewayWebSocket.name);
    
    // Clear any existing timers for this client before setting new ones
    this.clearClientTimers(clientId);

    const pingIntervalTimer = setInterval(() => {
      this.logger.log(`Sending ping to ${clientId}`, ApiGatewayWebSocket.name);
      client.emit('ping');
    }, this.heartbeatInterval);
    this.pingIntervalTimers.set(clientId, pingIntervalTimer);

    const newHeartbeatTimeoutTimer = setTimeout(() => {
      this.logger.warn(`Client ${clientId} heartbeat timeout. Disconnecting.`, ApiGatewayWebSocket.name);
      this.heartbeatTimeoutTimers.delete(clientId); // Remove self before disconnecting
      client.disconnect(true);
    }, this.heartbeatInterval * 2);
    this.heartbeatTimeoutTimers.set(clientId, newHeartbeatTimeoutTimer);

    client.on('pong', () => {
      this.logger.log(`Received pong from ${clientId}`, ApiGatewayWebSocket.name);
      // Clear the current timeout and set a new one if we want a sliding window
      const existingTimeout = this.heartbeatTimeoutTimers.get(clientId);
      if (existingTimeout) {
        clearTimeout(existingTimeout);
        this.heartbeatTimeoutTimers.delete(clientId);
      }
      // Optionally, re-set the timeout if a sliding window is desired for inactivity
      // For now, just clearing is fine, as disconnect will trigger cleanup.
      // Or, we can set a new timeout here to keep the connection alive as long as pongs are received.
      // Let's re-set it for robustness:
      const refreshedTimeout = setTimeout(() => {
        this.logger.warn(`Client ${clientId} heartbeat timeout after pong. Disconnecting.`, ApiGatewayWebSocket.name);
        this.heartbeatTimeoutTimers.delete(clientId);
        client.disconnect(true);
      }, this.heartbeatInterval * 2);
      this.heartbeatTimeoutTimers.set(clientId, refreshedTimeout);
    });
  }

  private clearClientTimers(clientId: string) {
    const pingTimer = this.pingIntervalTimers.get(clientId);
    if (pingTimer) {
      clearInterval(pingTimer);
      this.pingIntervalTimers.delete(clientId);
      this.logger.log(`Cleared ping interval for ${clientId}`, ApiGatewayWebSocket.name);
    }
    const heartbeatTimeout = this.heartbeatTimeoutTimers.get(clientId);
    if (heartbeatTimeout) {
      clearTimeout(heartbeatTimeout);
      this.heartbeatTimeoutTimers.delete(clientId);
      this.logger.log(`Cleared heartbeat timeout for ${clientId}`, ApiGatewayWebSocket.name);
    }
  }

  private cleanupClient(clientId: string) {
    this.logger.log(`cleanupClient for ${clientId}`, ApiGatewayWebSocket.name);
    this.clearClientTimers(clientId); // Centralized timer clearing
    this.connectedClients.delete(clientId);
    this.clientRooms.delete(clientId);
    // pingIntervalTimers and heartbeatTimeoutTimers are cleared in clearClientTimers
  }
}
