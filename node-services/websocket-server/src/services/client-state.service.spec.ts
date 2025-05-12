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
}); 