import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { WebSocketServerService } from './websocket-server.service';
import { WebSocketService } from '../websocket.service';
import { WebSocketMessage, WebSocketResponse } from '../interfaces/websocket-message.interface';

describe('WebSocketServerService', () => {
  let service: WebSocketServerService;
  let configService: ConfigService;
  let webSocketService: WebSocketService;

  const mockConfigService = {
    get: jest.fn(),
  };

  const mockWebSocketService = {
    sendToClient: jest.fn(),
    broadcastMessage: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        WebSocketServerService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: WebSocketService,
          useValue: mockWebSocketService,
        },
      ],
    }).compile();

    service = module.get<WebSocketServerService>(WebSocketServerService);
    configService = module.get<ConfigService>(ConfigService);
    webSocketService = module.get<WebSocketService>(WebSocketService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('sendMessage', () => {
    it('should queue message when not connected', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      const result = await service.sendMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not connected to WebSocket server');
    });

    it('should handle message timeout', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      // 模擬連接狀態
      (service as any).isConnected = true;
      (service as any).socket = {
        emit: jest.fn(),
      };

      const result = await service.sendMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Message timeout');
    });
  });

  describe('handleIncomingMessage', () => {
    it('should forward message to specific client', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
        clientId: 'test-client',
      };

      mockWebSocketService.sendToClient.mockResolvedValue({
        success: true,
        timestamp: new Date().toISOString(),
      });

      await (service as any).handleIncomingMessage(message);

      expect(mockWebSocketService.sendToClient).toHaveBeenCalledWith(
        message.clientId,
        message.event,
        message.data
      );
    });

    it('should broadcast message when no clientId specified', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      mockWebSocketService.broadcastMessage.mockResolvedValue({
        success: true,
        timestamp: new Date().toISOString(),
      });

      await (service as any).handleIncomingMessage(message);

      expect(mockWebSocketService.broadcastMessage).toHaveBeenCalledWith(
        message.event,
        message.data
      );
    });
  });
}); 