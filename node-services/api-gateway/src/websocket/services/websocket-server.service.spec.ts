import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { WebSocketServerService } from './websocket-server.service';
import { WebSocketService } from '../websocket.service';
import { WebSocketMessage, WebSocketResponse } from '../interfaces/websocket-message.interface';
import { LoggerService } from '@app/logger';

describe('WebSocketServerService', () => {
  let service: WebSocketServerService;
  let configService: ConfigService;
  let webSocketService: WebSocketService;
  let loggerService: LoggerService;

  const mockConfigService = {
    get: jest.fn(),
  };

  const mockWebSocketService = {
    sendToClient: jest.fn(),
    broadcastMessage: jest.fn(),
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
        WebSocketServerService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: WebSocketService,
          useValue: mockWebSocketService,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<WebSocketServerService>(WebSocketServerService);
    configService = module.get<ConfigService>(ConfigService);
    webSocketService = module.get<WebSocketService>(WebSocketService);
    loggerService = module.get<LoggerService>(LoggerService);
    
    // 添加 socket 模擬
    (service as any).socket = {
      emit: jest.fn(),
    };
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('sendMessage', () => {
    it('應該在未連接時將訊息加入佇列', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      const result = await service.sendMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not connected to WebSocket server');
    });

    it('應該能夠處理訊息超時', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      // 模擬連接狀態
      (service as any).isConnected = true;
      
      // 模擬 socket 行為
      const mockSocket = {
        emit: jest.fn((event, data, callback) => {
          // 不調用 callback，模擬超時情況
        }),
        on: jest.fn((event, callback) => {
          if (event === 'connect') {
            callback();
          }
        }),
      };
      (service as any).socket = mockSocket;

      // 模擬超時情況
      jest.useFakeTimers();
      
      const messagePromise = service.sendMessage(message);
      
      // 快進時間以觸發超時
      jest.advanceTimersByTime(5000);
      
      const result = await messagePromise;
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Message timeout');
      expect(mockSocket.emit).toHaveBeenCalledWith('message', message, expect.any(Function));
      
      // 清理
      jest.useRealTimers();
    });
  });

  describe('handleIncomingMessage', () => {
    it('應該能夠將訊息轉發給特定客戶端', async () => {
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

    it('應該能夠廣播訊息當沒有 clientId 指定時', async () => {
      const message: WebSocketMessage = {
        event: 'test-event',
        data: { test: 'data' },
        timestamp: new Date().toISOString(),
      };

      // 確保 socket 已經被正確初始化
      expect((service as any).socket).toBeDefined();
      
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