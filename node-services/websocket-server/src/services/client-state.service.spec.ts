import { Test, TestingModule } from '@nestjs/testing';
import { ClientStateService } from './client-state.service';
import { LoggerService } from '@app/logger';

describe('ClientStateService', () => {
  let service: ClientStateService;
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
        ClientStateService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<ClientStateService>(ClientStateService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('updateClientState', () => {
    it('應該正確更新客戶端狀態', () => {
      const socketId = 'test-socket-id';
      const state = {
        userId: 'user-123',
        room: 'test-room',
        status: 'online',
      };

      service.updateClientState(socketId, state);
      const result = service.getClientState(socketId);

      expect(result).toEqual(state);
    });

    it('應該正確合併部分更新', () => {
      const socketId = 'test-socket-id';
      const initialState = {
        userId: 'user-123',
        room: 'test-room',
      };
      const updateState = {
        status: 'online',
      };

      service.updateClientState(socketId, initialState);
      service.updateClientState(socketId, updateState);
      const result = service.getClientState(socketId);

      expect(result).toEqual({
        ...initialState,
        ...updateState,
      });
    });
  });

  describe('getClientState', () => {
    it('當客戶端不存在時應該返回 undefined', () => {
      const result = service.getClientState('non-existent-socket');
      expect(result).toBeUndefined();
    });

    it('應該正確獲取客戶端狀態', () => {
      const socketId = 'test-socket-id';
      const state = {
        userId: 'user-123',
        room: 'test-room',
      };

      service.updateClientState(socketId, state);
      const result = service.getClientState(socketId);

      expect(result).toEqual(state);
    });
  });

  describe('lastActivity 處理', () => {
    it('應該正確處理 lastActivity 屬性', () => {
      const socketId = 'test-socket-id';
      const now = new Date();
      const state = {
        userId: 'user-123',
        lastActivity: now,
      };

      service.updateClientState(socketId, state);
      const result = service.getClientState(socketId);

      expect(result?.lastActivity).toEqual(now);
    });
  });

  describe('undefined 值處理', () => {
    it('應該正確處理 undefined 值', () => {
      const socketId = 'test-socket-id';
      const initialState = {
        userId: 'user-123',
        room: 'test-room',
      };
      const updateState = {
        room: undefined,
      };

      service.updateClientState(socketId, initialState);
      service.updateClientState(socketId, updateState);
      const result = service.getClientState(socketId);

      expect(result).toEqual({
        userId: 'user-123',
        room: undefined,
      });
    });
  });

  describe('清除客戶端狀態', () => {
    it('應該成功清除存在的客戶端狀態', () => {
      const socketId = 'test-socket-id';
      const state = {
        userId: 'user-123',
        room: 'test-room',
      };

      service.updateClientState(socketId, state);
      const removeResult = service.removeClientState(socketId);
      const getResult = service.getClientState(socketId);

      expect(removeResult).toBe(true);
      expect(getResult).toBeUndefined();
    });

    it('清除不存在的客戶端狀態應該返回 false', () => {
      const removeResult = service.removeClientState('non-existent-socket');
      expect(removeResult).toBe(false);
    });
  });

  describe('多個客戶端操作', () => {
    it('應該正確處理多個客戶端的狀態', () => {
      const clients = [
        { id: 'client-1', state: { userId: 'user-1', room: 'room-1' } },
        { id: 'client-2', state: { userId: 'user-2', room: 'room-2' } },
        { id: 'client-3', state: { userId: 'user-3', room: 'room-1' } },
      ];

      // 設置多個客戶端狀態
      clients.forEach(client => {
        service.updateClientState(client.id, client.state);
      });

      // 驗證每個客戶端狀態
      clients.forEach(client => {
        const result = service.getClientState(client.id);
        expect(result).toEqual(client.state);
      });

      // 更新其中一個客戶端狀態
      const updatedState = { room: 'room-3' };
      service.updateClientState('client-1', updatedState);
      const result = service.getClientState('client-1');
      expect(result).toEqual({
        ...clients[0].state,
        ...updatedState,
      });
    });
  });

  describe('邊界條件測試', () => {
    it('應該正確處理空字串 socketId', () => {
      const state = { userId: 'user-123' };
      service.updateClientState('', state);
      const result = service.getClientState('');
      expect(result).toEqual(state);
    });

    it('應該正確處理特殊字符 socketId', () => {
      const specialIds = [
        'socket@123',
        'socket#456',
        'socket$789',
        'socket%abc',
        'socket^def',
        'socket&ghi',
      ];

      specialIds.forEach(id => {
        const state = { userId: `user-${id}` };
        service.updateClientState(id, state);
        const result = service.getClientState(id);
        expect(result).toEqual(state);
      });
    });

    it('應該正確處理非常長的 socketId', () => {
      const longId = 'x'.repeat(1000);
      const state = { userId: 'user-123' };
      service.updateClientState(longId, state);
      const result = service.getClientState(longId);
      expect(result).toEqual(state);
    });

    it('應該正確處理空狀態對象', () => {
      const socketId = 'test-socket-id';
      service.updateClientState(socketId, {});
      const result = service.getClientState(socketId);
      expect(result).toEqual({});
    });
  });
}); 