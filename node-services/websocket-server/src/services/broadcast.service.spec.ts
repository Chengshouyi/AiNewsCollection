import { Test, TestingModule } from '@nestjs/testing';
import { BroadcastService } from './broadcast.service';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

describe('BroadcastService', () => {
  let service: BroadcastService;
  let connectionPool: ConnectionPoolService;

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