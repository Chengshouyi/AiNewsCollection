import { Test, TestingModule } from '@nestjs/testing';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

describe('ConnectionPoolService', () => {
  let service: ConnectionPoolService;
  let loggerService: LoggerService;

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
        ConnectionPoolService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<ConnectionPoolService>(ConnectionPoolService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('連接管理', () => {
    it('應該正確添加和移除連接', () => {
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

    it('當添加重複的連接時應該覆蓋現有連接', () => {
      const mockSocket1 = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
      };
      const mockSocket2 = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
      };

      service.addConnection(mockSocket1 as any);
      service.addConnection(mockSocket2 as any);

      expect(service.getConnection('test-id')).toBe(mockSocket2);
    });

    it('當移除不存在的連接時不應該拋出錯誤', () => {
      expect(() => service.removeConnection('non-existent-id')).not.toThrow();
    });
  });

  describe('房間管理', () => {
    it('應該正確添加和移除用戶到房間', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
      };

      service.addConnection(mockSocket as any);
      service.addToRoom('test-id', 'test-room');

      expect(mockSocket.join).toHaveBeenCalledWith('test-room');
      expect(service.getRoomConnections('test-room')).toContain('test-id');

      service.removeFromRoom('test-id', 'test-room');
      expect(mockSocket.leave).toHaveBeenCalledWith('test-room');
      expect(service.getRoomConnections('test-room')).not.toContain('test-id');
    });

    it('當添加用戶到不存在的房間時應該創建新房間', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
      };

      service.addConnection(mockSocket as any);
      service.addToRoom('test-id', 'new-room');

      expect(service.getRoomConnections('new-room')).toContain('test-id');
    });

    it('當移除不存在的用戶時不應該拋出錯誤', () => {
      expect(() => service.removeFromRoom('non-existent-id', 'test-room')).not.toThrow();
    });

    it('應該正確獲取房間成員列表', () => {
      const mockSocket1 = {
        id: 'test-id-1',
        join: jest.fn(),
        leave: jest.fn(),
      };
      const mockSocket2 = {
        id: 'test-id-2',
        join: jest.fn(),
        leave: jest.fn(),
      };

      service.addConnection(mockSocket1 as any);
      service.addConnection(mockSocket2 as any);
      service.addToRoom('test-id-1', 'test-room');
      service.addToRoom('test-id-2', 'test-room');

      const members = service.getRoomConnections('test-room');
      expect(members.size).toBe(2);
      expect(members).toContain('test-id-1');
      expect(members).toContain('test-id-2');
    });

    it('當獲取不存在的房間成員時應該返回空陣列', () => {
      expect(service.getRoomConnections('non-existent-room')).toEqual(new Set());
    });
  });

  describe('連接查詢', () => {
    it('應該正確獲取連接', () => {
      const mockSocket = {
        id: 'test-id',
        join: jest.fn(),
        leave: jest.fn(),
      };

      service.addConnection(mockSocket as any);
      expect(service.getConnection('test-id')).toBe(mockSocket);
    });

    it('當獲取不存在的連接時應該返回 undefined', () => {
      expect(service.getConnection('non-existent-id')).toBeUndefined();
    });
  });
}); 