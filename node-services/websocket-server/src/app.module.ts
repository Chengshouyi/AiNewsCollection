import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health/health.controller';
import { RedisModule } from './shared/redis/redis.module';
import { TasksModule } from './tasks/tasks.module';
import { AppService } from './app.service';
import { MessageQueueService } from './message-queue.service';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true, // 全域可用
      envFilePath: '.env',
    }),
    TerminusModule,
    RedisModule,
    TasksModule,
  ],
  controllers: [HealthController],
  providers: [AppService, MessageQueueService],
  exports: [AppService, MessageQueueService]
})
export class AppModule {}
