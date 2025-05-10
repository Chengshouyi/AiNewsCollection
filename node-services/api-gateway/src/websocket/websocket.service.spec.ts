import { Test, TestingModule } from '@nestjs/testing';
import { WebSocketService } from './websocket.service';
import { ApiGatewayWebSocket } from './websocket.gateway';

describe('WebSocketService', () => {
  let service: WebSocketService;
  let gateway: ApiGatewayWebSocket;

  const mockGateway = {
    broadcastMessage: jest.fn(),
    sendToClient: jest.fn(),
    getConnectedClientsCount: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        WebSocketService,
        {
          provide: ApiGatewayWebSocket,
          useValue: mockGateway,
        },
      ],
    }).compile();

    service = module.get<WebSocketService>(WebSocketService);
    gateway = module.get<ApiGatewayWebSocket>(ApiGatewayWebSocket);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('broadcastMessage', () => {
    it('should broadcast message successfully', async () => {
      const event = 'test-event';
      const data = { message: 'test' };
      mockGateway.broadcastMessage.mockImplementation(() => {});

      const result = await service.broadcastMessage(event, data);

      expect(result.success).toBe(true);
      expect(result.event).toBe(event);
      expect(mockGateway.broadcastMessage).toHaveBeenCalledWith(event, data);
    });

    it('should handle broadcast error', async () => {
      const event = 'test-event';
      const data = { message: 'test' };
      mockGateway.broadcastMessage.mockImplementation(() => {
        throw new Error('Broadcast failed');
      });

      const result = await service.broadcastMessage(event, data);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Broadcast failed');
    });
  });

  describe('sendToClient', () => {
    it('should send message to client successfully', async () => {
      const clientId = 'test-client';
      const event = 'test-event';
      const data = { message: 'test' };
      mockGateway.sendToClient.mockImplementation(() => {});

      const result = await service.sendToClient(clientId, event, data);

      expect(result.success).toBe(true);
      expect(result.clientId).toBe(clientId);
      expect(result.event).toBe(event);
      expect(mockGateway.sendToClient).toHaveBeenCalledWith(clientId, event, data);
    });

    it('should handle send error', async () => {
      const clientId = 'test-client';
      const event = 'test-event';
      const data = { message: 'test' };
      mockGateway.sendToClient.mockImplementation(() => {
        throw new Error('Send failed');
      });

      const result = await service.sendToClient(clientId, event, data);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Send failed');
    });
  });

  describe('getConnectionStats', () => {
    it('should return connection stats', () => {
      const mockCount = 5;
      mockGateway.getConnectedClientsCount.mockReturnValue(mockCount);

      const result = service.getConnectionStats();

      expect(result.connectedClients).toBe(mockCount);
      expect(mockGateway.getConnectedClientsCount).toHaveBeenCalled();
    });

    it('should handle stats error', () => {
      mockGateway.getConnectedClientsCount.mockImplementation(() => {
        throw new Error('Stats failed');
      });

      const result = service.getConnectionStats();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Stats failed');
    });
  });
}); 