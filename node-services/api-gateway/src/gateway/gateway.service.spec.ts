import { Test, TestingModule } from '@nestjs/testing';
import { GatewayService } from './gateway.service';
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';

describe('GatewayService', () => {
  let service: GatewayService;
  let configService: ConfigService;
  let loggerService: LoggerService;

  const mockConfigService = {
    get: jest.fn().mockImplementation((key: string) => {
      if (key === 'PYTHON_BACKEND_URL') return 'http://python-backend';
      return null;
    }),
  };

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
        GatewayService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<GatewayService>(GatewayService);
    configService = module.get<ConfigService>(ConfigService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('getStatus', () => {
    it('應該返回正確的狀態信息', () => {
      const result = service.getStatus();

      expect(result).toEqual({
        status: 'ok',
        timestamp: expect.any(String),
        service: 'api-gateway',
        pythonBackendUrl: 'http://python-backend'
      });

      expect(mockLoggerService.log).toHaveBeenCalledWith('getStatus', 'GatewayService');
      expect(mockConfigService.get).toHaveBeenCalledWith('PYTHON_BACKEND_URL');
    });

    it('應該在沒有配置時返回 null 作為 pythonBackendUrl', () => {
      mockConfigService.get.mockReturnValueOnce(null);

      const result = service.getStatus();

      expect(result.pythonBackendUrl).toBeNull();
    });
  });
});
