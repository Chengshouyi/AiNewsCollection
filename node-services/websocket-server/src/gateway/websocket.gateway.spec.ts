import { Test, TestingModule } from '@nestjs/testing';
import { AppWebSocketGateway } from './websocket.gateway';
import { ConnectionPoolService } from '../services/connection-pool.service';
import { BroadcastService } from '../services/broadcast.service';
import { ClientStateService } from '../services/client-state.service';
import { MetricsService } from '../services/metrics.service';
import { ReconnectionService } from '../services/reconnection.service';
import { LoggerService } from '@app/logger';

describe('AppWebSocketGateway', () => {
  let gateway: AppWebSocketGateway;
  let connectionPool: ConnectionPoolService;
  let broadcastService: BroadcastService;
  let clientState: ClientStateService;
  let metrics: MetricsService;
  let reconnection: ReconnectionService;

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
        AppWebSocketGateway,
        ConnectionPoolService,
        BroadcastService,
        ClientStateService,
        ReconnectionService,
        MetricsService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    gateway = module.get<AppWebSocketGateway>(AppWebSocketGateway);
    connectionPool = module.get<ConnectionPoolService>(ConnectionPoolService);
    broadcastService = module.get<BroadcastService>(BroadcastService);
    clientState = module.get<ClientStateService>(ClientStateService);
    reconnection = module.get<ReconnectionService>(ReconnectionService);
    metrics = module.get<MetricsService>(MetricsService);
  });

  describe('handleConnection', () => {
    it('應該正確處理新的客戶端連線', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      };

      gateway.handleConnection(mockSocket as any);

      expect(connectionPool.getConnection('test-id')).toBeDefined();
      expect(metrics.getMetrics().activeConnections).toBe(1);
    });
  });

  describe('handleDisconnect', () => {
    it('應該正確處理客戶端斷線', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      };

      gateway.handleConnection(mockSocket as any);
      gateway.handleDisconnect(mockSocket as any);

      expect(connectionPool.getConnection('test-id')).toBeUndefined();
      expect(metrics.getMetrics().activeConnections).toBe(0);
    });
  });
});
