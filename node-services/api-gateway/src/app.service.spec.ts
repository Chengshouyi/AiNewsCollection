import { Test, TestingModule } from '@nestjs/testing';
import { AppService } from './app.service';
import { LoggerService } from '@app/logger';

describe('AppService', () => {
  let service: AppService;
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
        AppService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<AppService>(AppService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('getHello', () => {
    it('應該返回 "Hello World!"', () => {
      const result = service.getHello();
      expect(result).toBe('Hello World!');
      expect(mockLoggerService.log).toHaveBeenCalledWith('getHello', 'AppService');
    });
  });
});
