import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { RedisService } from '../shared/redis/redis.service';
import { ConfigService } from '@nestjs/config';
import { OnModuleInit } from '@nestjs/common';
import { LoggerService } from '@app/logger';

@WebSocketGateway({
  namespace: '/tasks', // 前端連線時用 io('/tasks')
  cors: {
    origin: '*', // 實際部署時請設為安全來源，改成只允許可信任的網域（例如 origin: 'https://yourdomain.com'），以提升安全性。
  },
})
export class TasksGateway implements OnModuleInit {

  constructor(
    private readonly redisService: RedisService,
    private readonly configService: ConfigService,
    private readonly logger: LoggerService,
  ) {
    // 需要從 .env 取得 REDIS_URL
    const redisUrl = this.configService.get<string>(
      'REDIS_URL',
      'redis://localhost:6379',
    );
    this.logger.log(`Redis URL: ${redisUrl}`);
  }

  @WebSocketServer()
  server: Server;

  // 客戶端連線時
  handleConnection(client: Socket) {
    this.logger.log(`客戶端已連線: ${client.id}`);
  }

  // 客戶端斷線時
  handleDisconnect(client: Socket) {
    this.logger.log(`客戶端已斷線: ${client.id}`);
  }

  // 客戶端請求加入房間
  @SubscribeMessage('join_room')
  handleJoinRoom(
    @MessageBody() data: { room: string },
    @ConnectedSocket() client: Socket,
  ) {
    client.join(data.room);
    client.emit('joined_room', { room: data.room });
    this.logger.log(`客戶端 ${client.id} 加入房間: ${data.room}`);
  }

  // 廣播訊息到房間
  broadcastToRoom(room: string, event: string, payload: any) {
    this.server.to(room).emit(event, payload);
  }

  onModuleInit() {
    // 訂閱 Redis 頻道，收到訊息時廣播給房間
    this.redisService.subscribe('task_events', (message) => {
      const { room, event, data } = message as unknown as {
        room: string;
        event: string;
        data: any;
      };
      this.server.to(room).emit(event, data);
      this.logger.debug(
        `已從 Redis 收到事件並廣播到房間: ${room}, 事件: ${event}`,
      );
    });
  }
}
