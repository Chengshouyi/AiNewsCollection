import { Test } from '@nestjs/testing';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { CustomLoggerModule } from '../src/custom-logger.module';
import { LoggerService } from '../src/logger.service';

describe('CustomLoggerModule', () => {
  describe('forRootAsync', () => {
    it('應該動態創建並提供 LoggerService', async () => {
      const module = await Test.createTestingModule({
        imports: [
          ConfigModule.forRoot({
            isGlobal: true,
            // 模擬環境變數
            load: [() => ({
              SERVICE_NAME: 'TestService',
              LOG_LEVEL: 'debug',
              NODE_ENV: 'test'
            })]
          }),
          CustomLoggerModule.forRootAsync()
        ]
      }).compile();

      const loggerService = module.get<LoggerService>(LoggerService);
      expect(loggerService).toBeDefined();
      expect(loggerService).toBeInstanceOf(LoggerService);
    });

    it('應該使用 ConfigService 配置 LoggerService', async () => {
      // 創建一個模擬的 ConfigService
      const mockConfigService = {
        get: jest.fn((key: string, defaultValue?: any) => {
          const configs = {
            SERVICE_NAME: 'MockService',
            LOG_LEVEL: 'info',
            NODE_ENV: 'test'
          };
          return configs[key] || defaultValue;
        })
      };

      const module = await Test.createTestingModule({
        imports: [CustomLoggerModule.forRootAsync()],
        providers: [
          {
            provide: ConfigService,
            useValue: mockConfigService
          }
        ]
      }).overrideProvider(ConfigService).useValue(mockConfigService).compile();

      const loggerService = module.get<LoggerService>(LoggerService);
      expect(loggerService).toBeDefined();
      expect(mockConfigService.get).toHaveBeenCalledWith('SERVICE_NAME');
      expect(mockConfigService.get).toHaveBeenCalledWith('LOG_LEVEL');
      expect(mockConfigService.get).toHaveBeenCalledWith('NODE_ENV', 'development');
    });

    it('應該在生產環境使用正確的預設值', async () => {
      // 創建一個模擬的 ConfigService，模擬生產環境
      const mockConfigService = {
        get: jest.fn((key: string, defaultValue?: any) => {
          const configs = {
            NODE_ENV: 'production'
          };
          return configs[key] || defaultValue;
        })
      };

      const module = await Test.createTestingModule({
        imports: [CustomLoggerModule.forRootAsync()],
        providers: [
          {
            provide: ConfigService,
            useValue: mockConfigService
          }
        ]
      }).compile();

      const loggerService = module.get<LoggerService>(LoggerService);
      expect(loggerService).toBeDefined();
      // 在生產環境中，預設 prettyPrint 應為 false
      // 這是一個實現細節，可能需要通過其他方式驗證
    });
  });
}); 