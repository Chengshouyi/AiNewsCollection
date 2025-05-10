import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health/health.controller';
import { RedisModule } from './shared/redis/redis.module';
import { TasksModule } from './tasks/tasks.module';
import { AppService } from './app.service';
import { MessageQueueService } from './services/message-queue.service';
import { CustomLoggerModule } from '@app/logger';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env', // 確保 SERVICE_NAME 和 LOG_LEVEL 在此定義
    }),
    CustomLoggerModule.forRootAsync(), // <-- 加入 CustomLoggerModule
    TerminusModule,
    RedisModule,
    TasksModule,
  ],
  controllers: [HealthController],
  providers: [AppService, MessageQueueService],
  exports: [AppService, MessageQueueService]
})
export class AppModule {}
