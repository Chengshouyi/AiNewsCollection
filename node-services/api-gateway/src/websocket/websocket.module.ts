import { Module } from '@nestjs/common';
import { ApiGatewayWebSocket } from './websocket.gateway';
import { WebSocketService } from './websocket.service';
import { WebSocketServerService } from './services/websocket-server.service';

@Module({
  providers: [ApiGatewayWebSocket, WebSocketService, WebSocketServerService],
  exports: [WebSocketService, WebSocketServerService],
})
export class WebSocketModule {}
