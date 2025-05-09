import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Swagger 設定 (如果尚未設定)
  const config = new DocumentBuilder()
    .setTitle('API Gateway')
    .setDescription('The API Gateway description')
    .setVersion('1.0')
    // .addTag('gateway') // 如果您想為 Gateway Controller 的 API 加標籤
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api-docs', app, document); // Swagger UI 將在 /api-docs 路徑提供

  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();
