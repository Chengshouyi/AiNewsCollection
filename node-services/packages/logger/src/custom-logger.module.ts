import { Module, Global, DynamicModule } from '@nestjs/common';
import { LoggerService, LoggerOptions } from './logger.service';
import { ConfigModule, ConfigService } from '@nestjs/config';

@Global() // 使 LoggerService 在 CustomLoggerModule 匯入 AppModule 後全局可用
@Module({})
export class CustomLoggerModule {
  static forRootAsync(): DynamicModule {
    return {
      module: CustomLoggerModule,
      imports: [ConfigModule], // 確保 ConfigModule 已匯入或在此處匯入
      providers: [
        {
          provide: LoggerService, // 這將是用於注入的令牌
          useFactory: (configService: ConfigService) => {
            // SERVICE_NAME 和 LOG_LEVEL 應在 .env 中定義並由 ConfigModule 加載
            const serviceName = configService.get<string>('SERVICE_NAME');
            const logLevel = configService.get<string>('LOG_LEVEL');
            const nodeEnv = configService.get<string>('NODE_ENV', 'development');

            const options: LoggerOptions = {
              level: logLevel || (nodeEnv === 'production' ? 'info' : 'debug'), // 更具體的預設級別
              serviceName: serviceName, // 這裡讓 ConfigService 決定預設值或讓其為 undefined
              prettyPrint: nodeEnv !== 'production', // 根據 NODE_ENV 決定是否美化輸出
            };
            return new LoggerService(options);
          },
          inject: [ConfigService],
        },
      ],
      exports: [LoggerService], // 匯出 LoggerService 以便在其他模組中注入
    };
  }
} 