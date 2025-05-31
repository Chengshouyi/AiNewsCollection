import { Test, TestingModule } from '@nestjs/testing';
import { HealthController } from './health.controller';
import {
  HealthCheckService,
  HttpHealthIndicator,
  HealthCheckStatus,
  HealthIndicatorStatus,
} from '@nestjs/terminus';
import { RedisService } from '../shared/redis/redis.service';
import { LoggerService } from '@app/logger';

describe('HealthController', () => {
  let controller: HealthController;
  let healthCheckService: HealthCheckService;
  let httpHealthIndicator: HttpHealthIndicator;
  let loggerService: LoggerService;

  const mockRedisClient = {
    ping: jest.fn(),
  };
  const mockLoggerService = {
    log: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(
        `[TEST LOG] ${context ? '[' + context + '] ' : ''}${message}`,
      );
    }),
    error: jest
      .fn()
      .mockImplementation((message: any, trace?: string, context?: string) => {
        console.error(
          `[TEST ERROR] ${context ? '[' + context + '] ' : ''}${message}${trace ? '\n' + trace : ''}`,
        );
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
      controllers: [HealthController],
      providers: [
        {
          provide: HealthCheckService,
          useValue: {
            check: jest.fn(),
          },
        },
        {
          provide: HttpHealthIndicator,
          useValue: {
            pingCheck: jest.fn(),
          },
        },
        {
          provide: RedisService,
          useValue: {
            getClient: jest.fn().mockReturnValue(mockRedisClient),
          },
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    controller = module.get<HealthController>(HealthController);
    healthCheckService = module.get<HealthCheckService>(HealthCheckService);
    httpHealthIndicator = module.get<HttpHealthIndicator>(HttpHealthIndicator);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(controller).toBeDefined();
  });

  describe('check', () => {
    it('應該可以成功執行健康檢查', async () => {
      const mockHealthCheckResult = {
        status: 'ok' as HealthCheckStatus,
        info: {
          nestjsDocs: { status: 'up' as HealthIndicatorStatus },
          redis: { status: 'up' as HealthIndicatorStatus },
        },
        details: {
          nestjsDocs: { status: 'up' as HealthIndicatorStatus },
          redis: { status: 'up' as HealthIndicatorStatus },
        },
      };

      jest
        .spyOn(healthCheckService, 'check')
        .mockImplementation(async (checks) => {
          await Promise.all(checks.map((check) => check()));
          return mockHealthCheckResult;
        });
      jest
        .spyOn(httpHealthIndicator, 'pingCheck')
        .mockResolvedValue({ nestjsDocs: { status: 'up' } });
      mockRedisClient.ping.mockResolvedValue('PONG');

      const result = await controller.check();

      expect(result).toEqual(mockHealthCheckResult);
      expect(() => loggerService.log('check_health')).toHaveBeenCalled();
      expect(() =>
        loggerService.log('redis_ping_success', 'HealthController'),
      ).toHaveBeenCalled();
    });

    it('應該可以處理Redis ping失敗', async () => {
      const mockError = new Error('Redis connection failed');
      mockRedisClient.ping.mockRejectedValue(mockError);

      const mockHealthCheckResult = {
        status: 'error' as HealthCheckStatus,
        error: {
          redis: {
            status: 'down' as HealthIndicatorStatus,
            message: 'Redis connection failed',
          },
        },
        details: {
          redis: {
            status: 'down' as HealthIndicatorStatus,
            message: 'Redis connection failed',
          },
        },
      };

      jest
        .spyOn(healthCheckService, 'check')
        .mockImplementation(async (checks) => {
          await Promise.all(checks.map((check) => check()));
          return mockHealthCheckResult;
        });

      const result = await controller.check();

      expect(result).toEqual(mockHealthCheckResult);
      expect(() =>
        loggerService.error('redis_ping_failed', mockError, 'HealthController'),
      ).toHaveBeenCalled();
    });
  });
});
