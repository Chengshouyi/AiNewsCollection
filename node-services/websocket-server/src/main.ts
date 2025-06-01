import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { Server as HttpServer } from 'http';
import { Server } from 'socket.io';
import { AppService } from './app.service';
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';

export async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: false,
  });

  const appLogger = app.get(LoggerService);
  app.useLogger(appLogger);

  const configService = app.get(ConfigService);

  // 創建 HTTP 服務器
  const httpServer: HttpServer = app.getHttpServer() as unknown as HttpServer;

  // 創建 Socket.IO 服務器
  const io = new Server(httpServer, {
    cors: {
      origin: configService.get<string>('CORS_ORIGIN', '*'),
      methods: ['GET', 'POST'],
      credentials: true,
    },
    path: '/socket.io',
  });

  // 獲取 AppService 實例並設置 Socket.IO 服務器
  const appService = app.get(AppService);
  appService.setSocketServer(io);

  // 監聽連接事件
  io.on('connection', (socket) => {
    appLogger.log(`Client connected: ${socket.id}`, 'SocketConnection');

    // 處理加入房間
    socket.on('join_room', (data) => {
      const { room } = data as { room: string };
      void socket.join(room);
      appLogger.log(`Client ${socket.id} joined room: ${room}`, 'SocketRoom');
    });

    // 處理離開房間
    socket.on('leave_room', (data) => {
      const { room } = data as { room: string };
      void socket.leave(room);
      appLogger.log(`Client ${socket.id} left room: ${room}`, 'SocketRoom');
    });

    // 處理斷開連接
    socket.on('disconnect', () => {
      appLogger.log(`Client disconnected: ${socket.id}`, 'SocketConnection');
    });

    socket.on('error', (error) => {
      appLogger.error(
        `Socket error for client ${socket.id}`,
        error,
        'SocketError',
      );
    });

    // 新增心跳檢測
    socket.on('ping', () => {
      socket.emit('pong');
    });
  });

  // 從配置中讀取端口
  const port = configService.get<number>('PORT') || 15001;
  httpServer.listen(port);
  appLogger.log(`WebSocket Server is running on port: ${port}`, 'Bootstrap');
}
