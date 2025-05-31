import { Test, TestingModule } from '@nestjs/testing';
import { BroadcastService } from './broadcast.service';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';
import { Socket } from 'socket.io';

describe('BroadcastService', () => {
  let service: BroadcastService;
  let connectionPool: ConnectionPoolService;

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

  it('應該正確廣播訊息到房間', () => {
    const mockEmit = jest.fn().mockReturnValue(true);
    const mockJoin = jest.fn().mockReturnValue(undefined);
    const mockSocket = {
      id: 'test-id',
      emit: mockEmit,
      join: mockJoin,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    connectionPool.addToRoom('test-id', 'test-room');

    service.broadcastToRoom('test-room', 'test-event', { data: 'test' });
    expect(mockEmit).toHaveBeenCalledWith('test-event', {
      data: 'test',
    });
    expect(mockJoin).toHaveBeenCalledWith('test-room');
  });

  it('應該正確廣播訊息到所有連接', () => {
    const mockEmit1 = jest.fn().mockReturnValue(true);
    const mockJoin1 = jest.fn().mockReturnValue(undefined);
    const mockEmit2 = jest.fn().mockReturnValue(true);
    const mockJoin2 = jest.fn().mockReturnValue(undefined);
    const mockSocket1 = {
      id: 'test-id-1',
      emit: mockEmit1,
      join: mockJoin1,
    } as Partial<Socket> as Socket;
    const mockSocket2 = {
      id: 'test-id-2',
      emit: mockEmit2,
      join: mockJoin2,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket1);
    connectionPool.addConnection(mockSocket2);

    service.broadcastToAll('test-event', { data: 'test' });

    expect(mockEmit1).toHaveBeenCalledWith('test-event', {
      data: 'test',
    });
    expect(mockEmit2).toHaveBeenCalledWith('test-event', {
      data: 'test',
    });
  });

  it('處理空房間的情況', () => {
    const mockEmit = jest.fn().mockReturnValue(true);
    const mockJoin = jest.fn().mockReturnValue(undefined);
    const mockSocket = {
      id: 'test-id',
      emit: mockEmit,
      join: mockJoin,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    // 不將 socket 加入任何房間

    service.broadcastToRoom('empty-room', 'test-event', { data: 'test' });

    expect(mockEmit).not.toHaveBeenCalled();
  });

  it('處理無效 socket 的情況', () => {
    const mockEmit = jest.fn().mockReturnValue(true);
    const mockJoin = jest.fn().mockReturnValue(undefined);
    const mockSocket = {
      id: 'test-id',
      emit: mockEmit,
      join: mockJoin,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    connectionPool.addToRoom('test-id', 'test-room');

    // 模擬 socket 被移除的情況
    connectionPool.removeConnection('test-id');

    service.broadcastToRoom('test-room', 'test-event', { data: 'test' });

    expect(mockEmit).not.toHaveBeenCalled();
  });

  it('處理 socket emit 錯誤的情況', () => {
    const mockSocket = {
      id: 'test-id',
      emit: jest.fn().mockImplementation(() => {
        throw new Error('Emit failed');
      }),
      join: jest.fn().mockReturnValue(undefined),
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    connectionPool.addToRoom('test-id', 'test-room');

    // 確保錯誤不會中斷執行
    expect(() =>
      service.broadcastToRoom('test-room', 'test-event', { data: 'test' }),
    ).not.toThrow();

    expect(mockLoggerService.error).toHaveBeenCalled();
  });

  it('處理大量 socket 的情況', () => {
    const socketCount = 100;
    const mockSockets = Array.from({ length: socketCount }, (_, index) => ({
      id: `test-id-${index}`,
      emit: jest.fn().mockReturnValue(true),
      join: jest.fn().mockReturnValue(undefined),
    }));

    // 添加所有 socket 到連接池
    mockSockets.forEach((socket) => {
      connectionPool.addConnection(socket as Partial<Socket> as Socket);
      connectionPool.addToRoom(socket.id, 'large-room');
    });

    service.broadcastToRoom('large-room', 'test-event', { data: 'test' });

    // 驗證所有 socket 都收到了訊息
    mockSockets.forEach((socket) => {
      expect(socket.emit).toHaveBeenCalledWith('test-event', { data: 'test' });
      expect(socket.join).toHaveBeenCalledWith('large-room');
    });
  });

  it('處理不同類型的訊息數據', () => {
    const mockEmit = jest.fn().mockReturnValue(true);
    const mockJoin = jest.fn().mockReturnValue(undefined);
    const mockSocket = {
      id: 'test-id',
      emit: mockEmit,
      join: mockJoin,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    connectionPool.addToRoom('test-id', 'test-room');

    const testCases = [
      { type: 'string', data: 'test string' },
      { type: 'number', data: 123 },
      { type: 'boolean', data: true },
      { type: 'object', data: { key: 'value' } },
      { type: 'array', data: [1, 2, 3] },
      { type: 'null', data: null },
    ];

    for (const testCase of testCases) {
      service.broadcastToRoom('test-room', 'test-event', testCase.data);
      expect(mockEmit).toHaveBeenCalledWith('test-event', testCase.data);
    }
  });

  it('處理並發廣播的情況', async () => {
    const mockEmit = jest.fn().mockReturnValue(true);
    const mockJoin = jest.fn().mockReturnValue(undefined);
    const mockSocket = {
      id: 'test-id',
      emit: mockEmit,
      join: mockJoin,
    } as Partial<Socket> as Socket;

    connectionPool.addConnection(mockSocket);
    connectionPool.addToRoom('test-id', 'test-room');

    // 模擬多個並發廣播
    const broadcastPromises = Array.from({ length: 5 }, (_, index) =>
      service.broadcastToRoom('test-room', 'test-event', { index }),
    );

    await Promise.all(broadcastPromises);

    // 驗證所有廣播都成功執行
    expect(mockEmit).toHaveBeenCalledTimes(5);

    // 驗證每個廣播的順序
    for (let i = 0; i < 5; i++) {
      expect(mockEmit).toHaveBeenNthCalledWith(i + 1, 'test-event', {
        index: i,
      });
    }
  });
});
