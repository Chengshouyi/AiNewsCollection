import { WebSocketGateway, WebSocketServer, OnGatewayConnection, OnGatewayDisconnect, OnGatewayInit, SubscribeMessage } from '@nestjs/websockets';
import { Server, Socket, Namespace } from 'socket.io';
// import { Logger } from '@nestjs/common'; // Temporarily comment out Logger
import { ConfigService } from '@nestjs/config';

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

  constructor(private readonly configService: ConfigService) {
    console.log('[GATEWAY] ApiGatewayWebSocket CONSTRUCTOR called');
    this.heartbeatInterval = this.configService.get('WEBSOCKET_HEARTBEAT_INTERVAL', 30000);
    console.log(`[GATEWAY] Heartbeat interval set to: ${this.heartbeatInterval}`);
  }

  afterInit(server: Namespace) {
    console.log('[GATEWAY] ApiGatewayWebSocket AFTERINIT called');
    if (server) {
      console.log(`[GATEWAY] afterInit: server argument name: ${server.name}`);
      console.log(`[GATEWAY] afterInit: this.server name: ${this.server?.name}`);
    } else {
      console.log('[GATEWAY] afterInit: server argument is NULL or UNDEFINED');
    }
  }

  handleConnection(client: Socket) {
    const clientId = client.id;
    this.connectedClients.set(clientId, client);
    this.clientRooms.set(clientId, new Set());
    console.log(`[GATEWAY] Client connected: ${clientId} - handleConnection START, in namespace: ${client.nsp.name}`);
    
    console.log(`[GATEWAY] Calling setupHeartbeat for ${clientId}`);
    this.setupHeartbeat(client);
    console.log(`[GATEWAY] Finished setupHeartbeat for ${clientId}`);

    console.log(`[GATEWAY] Attempting to send 'welcome' message to ${clientId}`);
    client.emit('welcome', {
      message: 'Welcome to API Gateway WebSocket',
      clientId,
      timestamp: new Date().toISOString()
    });
    console.log(`[GATEWAY] 'welcome' message sent to ${clientId}`);
  }

  handleDisconnect(client: Socket) {
    const clientId = client.id;
    console.log(`[GATEWAY] handleDisconnect for ${clientId} - calling cleanupClient`); // Added log
    this.cleanupClient(clientId);
    console.log(`[GATEWAY] Client disconnected: ${clientId}`);
  }

  @SubscribeMessage('join_room')
  handleJoinRoom(client: Socket, data: { room: string }) {
    const clientId = client.id;
    const { room } = data;
    console.log(`[GATEWAY] handleJoinRoom called by ${clientId} for room ${room}`);
    try {
      client.join(room);
      const rooms = this.clientRooms.get(clientId) || new Set();
      rooms.add(room);
      this.clientRooms.set(clientId, rooms);

      console.log(`[GATEWAY] Client ${clientId} joined room: ${room}`);
      client.emit('room_joined', {
        room,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error(`[GATEWAY] Error joining room for ${clientId}: ${error.message}`);
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
    console.log(`[GATEWAY] handleLeaveRoom called by ${clientId} for room ${room}`);
    try {
      client.leave(room);
      const rooms = this.clientRooms.get(clientId);
      if (rooms) {
        rooms.delete(room);
      }

      console.log(`[GATEWAY] Client ${clientId} left room: ${room}`);
      client.emit('room_left', {
        room,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error(`[GATEWAY] Error leaving room for ${clientId}: ${error.message}`);
      client.emit('error', {
        message: 'Failed to leave room',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }

  @SubscribeMessage('ping')
  handlePing(client: Socket) {
    console.log(`[GATEWAY] handlePing called by ${client.id}`);
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
  }

  // 發送訊息給特定客戶端
  sendToClient(clientId: string, event: string, data: any) {
    const client = this.connectedClients.get(clientId);
    if (client) {
      client.emit(event, {
        ...data,
        timestamp: new Date().toISOString()
      });
    }
  }

  // 發送訊息給特定房間
  sendToRoom(room: string, event: string, data: any) {
    this.server.to(room).emit(event, {
      ...data,
      timestamp: new Date().toISOString()
    });
  }

  // 獲取當前連接的客戶端數量
  getConnectedClientsCount(): number {
    return this.connectedClients.size;
  }

  // 獲取客戶端所在的房間
  getClientRooms(clientId: string): string[] {
    const rooms = this.clientRooms.get(clientId);
    return rooms ? Array.from(rooms) : [];
  }

  private setupHeartbeat(client: Socket) {
    const clientId = client.id;
    console.log(`[GATEWAY] setupHeartbeat for ${clientId}`);
    
    // Clear any existing timers for this client before setting new ones
    this.clearClientTimers(clientId);

    const pingIntervalTimer = setInterval(() => {
      console.log(`[GATEWAY] Sending ping to ${clientId}`); // Added log
      client.emit('ping');
    }, this.heartbeatInterval);
    this.pingIntervalTimers.set(clientId, pingIntervalTimer);

    const newHeartbeatTimeoutTimer = setTimeout(() => {
      console.warn(`[GATEWAY] Client ${clientId} heartbeat timeout. Disconnecting.`);
      this.heartbeatTimeoutTimers.delete(clientId); // Remove self before disconnecting
      client.disconnect(true);
    }, this.heartbeatInterval * 2);
    this.heartbeatTimeoutTimers.set(clientId, newHeartbeatTimeoutTimer);

    client.on('pong', () => {
      console.log(`[GATEWAY] Received pong from ${clientId}`); // Added log
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
        console.warn(`[GATEWAY] Client ${clientId} heartbeat timeout after pong. Disconnecting.`);
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
      console.log(`[GATEWAY] Cleared ping interval for ${clientId}`);
    }
    const heartbeatTimeout = this.heartbeatTimeoutTimers.get(clientId);
    if (heartbeatTimeout) {
      clearTimeout(heartbeatTimeout);
      this.heartbeatTimeoutTimers.delete(clientId);
      console.log(`[GATEWAY] Cleared heartbeat timeout for ${clientId}`);
    }
  }

  private cleanupClient(clientId: string) {
    console.log(`[GATEWAY] cleanupClient for ${clientId}`);
    this.clearClientTimers(clientId); // Centralized timer clearing
    this.connectedClients.delete(clientId);
    this.clientRooms.delete(clientId);
    // pingIntervalTimers and heartbeatTimeoutTimers are cleared in clearClientTimers
  }
}
