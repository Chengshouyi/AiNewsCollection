@WebSocketGateway({
  namespace: '/ws',
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
  },
})
export class WebSocketGateway implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect {
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
    this.connectionPool.addConnection(client);
    this.metrics.recordConnection();
    this.logger.log(`客戶端已連線: ${client.id}`);
  }

  handleDisconnect(client: Socket) {
    this.connectionPool.removeConnection(client.id);
    this.metrics.recordDisconnection();
    this.logger.log(`客戶端已斷線: ${client.id}`);
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
