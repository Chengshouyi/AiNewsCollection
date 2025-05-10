import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health/health.controller';
import { RedisModule } from './shared/redis/redis.module';
import { TasksModule } from './tasks/tasks.module';
import { AppService } from './app.service';
import { MessageQueueService } from './services/message-queue.service';
import { WebSocketGateway } from '@nestjs/websockets';
import { WebSocketModule } from './websocket/websocket.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    TerminusModule,
    RedisModule,
    TasksModule,
    WebSocketModule,
  ],
  controllers: [HealthController],
  providers: [AppService, MessageQueueService],
  exports: [AppService, MessageQueueService]
})
export class AppModule {}
