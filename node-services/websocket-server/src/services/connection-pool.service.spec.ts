import { Test, TestingModule } from '@nestjs/testing';
import { ConnectionPoolService } from './connection-pool.service';
import { LoggerService } from '@app/logger';

describe('ConnectionPoolService', () => {
  let service: ConnectionPoolService;

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