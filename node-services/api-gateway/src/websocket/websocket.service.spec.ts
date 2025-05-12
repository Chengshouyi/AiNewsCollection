import { Test, TestingModule } from '@nestjs/testing';
import { WebSocketService } from './websocket.service';
import { ApiGatewayWebSocket } from './websocket.gateway';
import { LoggerService } from '@app/logger';

describe('WebSocketService', () => {
  let service: WebSocketService;
  let gateway: ApiGatewayWebSocket;

  const mockGateway = {
    broadcastMessage: jest.fn(),
    sendToClient: jest.fn(),
    getConnectedClientsCount: jest.fn(),
  };

  const mockLoggerService = {
    log: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(`[TEST LOG] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    error: jest.fn().mockImplementation((message: any, trace?: string, context?: string) => {
      console.error(`[TEST ERROR] ${context ? '[' + context + '] ' : ''}${message}${trace ? '\n' + trace : ''}`);
    }),
    warn: jest.fn().mockImplementation((message: any, context?: string) => {
      console.warn(`[TEST WARN] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    debug: jest.fn().mockImplementation((message: any, context?: string) => {
      console.debug(`[TEST DEBUG] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    verbose: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(`[TEST VERBOSE] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
  };


  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        WebSocketService,
        {
          provide: ApiGatewayWebSocket,
          useValue: mockGateway,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<WebSocketService>(WebSocketService);
    gateway = module.get<ApiGatewayWebSocket>(ApiGatewayWebSocket);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('broadcastMessage', () => {
    it('應該能夠廣播訊息成功', async () => {
      const event = 'test-event';
      const data = { message: 'test' };
      mockGateway.broadcastMessage.mockImplementation(() => {});

      const result = await service.broadcastMessage(event, data);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.event).toBe(event);
      }
      expect(mockGateway.broadcastMessage).toHaveBeenCalledWith(event, data);
    });

    it('應該能夠處理廣播錯誤', async () => {
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
    it('應該能夠發送訊息給客戶端成功', async () => {
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

    it('應該能夠處理發送錯誤', async () => {
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
    it('應該能夠返回連接統計資訊', () => {
      const mockCount = 5;
      mockGateway.getConnectedClientsCount.mockReturnValue(mockCount);

      const result = service.getConnectionStats();

      expect(result.connectedClients).toBe(mockCount);
      expect(mockGateway.getConnectedClientsCount).toHaveBeenCalled();
    });

    it('應該能夠處理統計錯誤', () => {
      mockGateway.getConnectedClientsCount.mockImplementation(() => {
        throw new Error('Stats failed');
      });

      const result = service.getConnectionStats();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Stats failed');
    });
  });
}); 