import { Test, TestingModule } from '@nestjs/testing';
import { AppWebSocketGateway } from './websocket.gateway';
import { ConnectionPoolService } from '../services/connection-pool.service';
import { BroadcastService } from '../services/broadcast.service';
import { ClientStateService } from '../services/client-state.service';
import { MetricsService } from '../services/metrics.service';
import { ReconnectionService } from '../services/reconnection.service';
import { LoggerService } from '@app/logger';
import { Socket } from 'socket.io';

describe('AppWebSocketGateway', () => {
  let gateway: AppWebSocketGateway;
  let connectionPool: ConnectionPoolService;
  let metrics: MetricsService;
  let reconnection: ReconnectionService;

  const mockLoggerService = {
    log: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(
        `[TEST LOG] ${context ? '[' + context + '] ' : ''}${message}`,
      );
    }),
    error: jest
      .fn()
      .mockImplementation((message: any, trace?: string, context?: string) => {
        if (trace) {
          console.error(
            `[TEST ERROR] ${context ? '[' + context + '] ' : ''}${message}${trace ? '\n' + trace : ''}`,
          );
        } else {
          console.error(`[TEST ERROR] ${message}`);
        }
      }),
    warn: jest.fn().mockImplementation((message: any, context?: string) => {
      console.warn(
        `[TEST WARN] ${context ? '[' + context + '] ' : ''}${message}`,
      );
    }),
    debug: jest.fn().mockImplementation((message: any, context?: string) => {
      console.debug(
        `[TEST DEBUG] ${context ? '[' + context + '] ' : ''}${message}`,
      );
    }),
    verbose: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(
        `[TEST VERBOSE] ${context ? '[' + context + '] ' : ''}${message}`,
      );
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
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);

      expect(connectionPool.getConnection('test-id')).toBeDefined();
      expect(metrics.getMetrics().activeConnections).toBe(1);
    });

    it('應該處理重複連線的情況', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleConnection(mockSocket);

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
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleDisconnect(mockSocket);

      expect(connectionPool.getConnection('test-id')).toBeUndefined();
      expect(metrics.getMetrics().activeConnections).toBe(0);
    });

    it('應該處理未知客戶端斷線的情況', () => {
      const mockSocket = {
        id: 'unknown-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      } as Partial<Socket> as Socket;

      gateway.handleDisconnect(mockSocket);
      expect(metrics.getMetrics().activeConnections).toBe(0);
    });
  });

  describe('handleJoinRoom', () => {
    it('應該正確處理加入房間的請求', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleJoinRoom({ room: 'test-room' }, mockSocket);

      const roomConnections = connectionPool.getRoomConnections('test-room');
      expect(roomConnections.has('test-id')).toBe(true);
    });

    it('應該處理加入多個房間的情況', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleJoinRoom({ room: 'room1' }, mockSocket);
      gateway.handleJoinRoom({ room: 'room2' }, mockSocket);

      expect(connectionPool.getRoomConnections('room1').has('test-id')).toBe(
        true,
      );
      expect(connectionPool.getRoomConnections('room2').has('test-id')).toBe(
        true,
      );
    });
  });

  describe('錯誤處理', () => {
    it('應該處理無效的房間加入請求', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleJoinRoom({ room: '' }, mockSocket);

      expect(connectionPool.getRoomConnections('')).toBeDefined();
    });

    it('應該處理斷線後重新連線的情況', async () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
        emit: jest.fn(),
        connected: true,
      } as Partial<Socket> as Socket;

      gateway.handleConnection(mockSocket);
      gateway.handleDisconnect(mockSocket);
      await reconnection.handleReconnection(mockSocket);
      gateway.handleConnection(mockSocket);

      expect(connectionPool.getConnection('test-id')).toBeDefined();
      expect(metrics.getMetrics().activeConnections).toBe(1);
    });
  });
});
