import { Test, TestingModule } from '@nestjs/testing';
import { WebSocketGateway } from './websocket.gateway';
import { ConnectionPoolService } from '../services/connection-pool.service';
import { BroadcastService } from '../services/broadcast.service';
import { ClientStateService } from '../services/client-state.service';
import { MetricsService } from '../services/metrics.service';
import { LoggerService } from '@app/logger';

describe('WebSocketGateway', () => {
  let gateway: WebSocketGateway;
  let connectionPool: ConnectionPoolService;
  let broadcastService: BroadcastService;
  let clientState: ClientStateService;
  let metrics: MetricsService;

  const mockLoggerService = {
    log: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    debug: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        WebSocketGateway,
        ConnectionPoolService,
        BroadcastService,
        ClientStateService,
        MetricsService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    gateway = module.get<WebSocketGateway>(WebSocketGateway);
    connectionPool = module.get<ConnectionPoolService>(ConnectionPoolService);
    broadcastService = module.get<BroadcastService>(BroadcastService);
    clientState = module.get<ClientStateService>(ClientStateService);
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

// src/services/connection-pool.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

describe('ConnectionPoolService', () => {
  let service: ConnectionPoolService;

  const mockLoggerService = {
    log: jest.fn(),
    error: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ConnectionPoolService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<ConnectionPoolService>(ConnectionPoolService);
  });

  it('應該正確管理連接池', () => {
    const mockSocket = {
      id: 'test-id',
      join: jest.fn(),
      leave: jest.fn(),
    };

    service.addConnection(mockSocket as any);
    expect(service.getConnection('test-id')).toBeDefined();

    service.removeConnection('test-id');
    expect(service.getConnection('test-id')).toBeUndefined();
  });
});

// src/services/broadcast.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { BroadcastService } from './broadcast.service';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

describe('BroadcastService', () => {
  let service: BroadcastService;
  let connectionPool: ConnectionPoolService;

  const mockLoggerService = {
    log: jest.fn(),
    error: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        BroadcastService,
        ConnectionPoolService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<BroadcastService>(BroadcastService);
    connectionPool = module.get<ConnectionPoolService>(ConnectionPoolService);
  });

  it('應該正確廣播訊息到房間', async () => {
    const mockSocket = {
      id: 'test-id',
      emit: jest.fn(),
    };

    connectionPool.addConnection(mockSocket as any);
    connectionPool.addToRoom('test-id', 'test-room');

    await service.broadcastToRoom('test-room', 'test-event', { data: 'test' });

    expect(mockSocket.emit).toHaveBeenCalledWith('test-event', { data: 'test' });
  });
});
