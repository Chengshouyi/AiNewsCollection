import { Module } from '@nestjs/common';
import { WebSocketGateway } from '@nestjs/websockets';
import { WebSocketService } from './websocket.service';

@Module({
  providers: [WebSocketService],
  exports: [WebSocketService],
})
export class WebSocketModule {}
