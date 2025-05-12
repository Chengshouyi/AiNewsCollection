import { WebSocketGateway, OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect, SubscribeMessage, MessageBody, ConnectedSocket } from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { ConnectionPoolService } from '../services/connection-pool.service';
import { BroadcastService } from '../services/broadcast.service';
import { ClientStateService } from '../services/client-state.service';
import { ReconnectionService } from '../services/reconnection.service';
import { MetricsService } from '../services/metrics.service';
import { LoggerService } from '@app/logger';

@WebSocketGateway({
  namespace: '/ws',
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
  },
})
export class AppWebSocketGateway implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect {
  constructor(
    private readonly connectionPool: ConnectionPoolService,
    private readonly broadcastService: BroadcastService,
    private readonly clientState: ClientStateService,
    private readonly reconnection: ReconnectionService,
    private readonly metrics: MetricsService,
    private readonly logger: LoggerService,
  ) {}

  afterInit(server: Server) {
    this.logger.log('WebSocket 閘道已初始化');
  }

  handleConnection(client: Socket) {
    const existingConnection = this.connectionPool.getConnection(client.id);
    if (!existingConnection) {
      this.connectionPool.addConnection(client);
      this.metrics.recordConnection();
      this.logger.log(`客戶端已連線: ${client.id}`);
    }
  }

  handleDisconnect(client: Socket) {
    const existingConnection = this.connectionPool.getConnection(client.id);
    if (existingConnection) {
      this.connectionPool.removeConnection(client.id);
      this.metrics.recordDisconnection();
      this.logger.log(`客戶端已斷線: ${client.id}`);
    }
  }

  @SubscribeMessage('join_room')
  handleJoinRoom(
    @MessageBody() data: { room: string },
    @ConnectedSocket() client: Socket,
  ) {
    this.connectionPool.addToRoom(client.id, data.room);
    this.broadcastService.broadcastToRoom(
      data.room,
      'user_joined',
      { userId: client.id }
    );
  }
}
