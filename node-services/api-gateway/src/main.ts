import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { LoggerService } from '@app/logger';
import { ConfigService } from '@nestjs/config';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: false,
  });

  const appLogger = app.get(LoggerService);
  app.useLogger(appLogger);

  const configService = app.get(ConfigService);

  // Swagger 設定 (如果尚未設定)
  const config = new DocumentBuilder()
    .setTitle('API Gateway')
    .setDescription('The API Gateway description')
    .setVersion('1.0')
    // .addTag('gateway') // 如果您想為 Gateway Controller 的 API 加標籤
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api-docs', app, document); // Swagger UI 將在 /api-docs 路徑提供

  const port = configService.get<number>('PORT') || 3000;
  await app.listen(port);
  appLogger.log(`API Gateway is running on: http://localhost:${port}/api-docs`, 'Bootstrap');
}
bootstrap();
