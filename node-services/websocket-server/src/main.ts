import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { AppService } from './app.service';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // 創建 HTTP 服務器
  const httpServer = createServer(app.getHttpAdapter().getInstance());
  
  // 創建 Socket.IO 服務器
  const io = new Server(httpServer, {
    cors: {
      origin: '*', // 在生產環境中應該設置具體的域名
      methods: ['GET', 'POST'],
      credentials: true
    },
    path: '/socket.io'
  });

  // 獲取 AppService 實例並設置 Socket.IO 服務器
  const appService = app.get(AppService);
  appService.setSocketServer(io);

  // 監聽連接事件
  io.on('connection', (socket) => {
    console.log('Client connected:', socket.id);

    // 處理加入房間
    socket.on('join_room', (data) => {
      const { room } = data;
      socket.join(room);
      console.log(`Client ${socket.id} joined room: ${room}`);
    });

    // 處理離開房間
    socket.on('leave_room', (data) => {
      const { room } = data;
      socket.leave(room);
      console.log(`Client ${socket.id} left room: ${room}`);
    });

    // 處理斷開連接
    socket.on('disconnect', () => {
      console.log('Client disconnected:', socket.id);
    });

    socket.on('error', (error) => {
        console.error(`Socket error for client ${socket.id}:`, error);
    });

    // 新增心跳檢測
    socket.on('ping', () => {
        socket.emit('pong');
    });
  });

  // 啟動服務器
  const port = process.env.PORT || 3000;
  await httpServer.listen(port);
  console.log(`Application is running on: ${await app.getUrl()}`);
}
bootstrap();
