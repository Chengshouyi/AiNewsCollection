import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TerminusModule } from '@nestjs/terminus';
import { JwtModule } from '@nestjs/jwt';
import { HealthController } from './health/health.controller';
import { RedisModule } from './shared/redis/redis.module';
import { TasksModule } from './tasks/tasks.module';
import { AppService } from './app.service';
import { MessageQueueService } from './services/message-queue.service';
import { CustomLoggerModule } from '@app/logger';

// 新增的服務
import { ConnectionPoolService } from './services/connection-pool.service';
import { BroadcastService } from './services/broadcast.service';
import { ClientStateService } from './services/client-state.service';
import { ReconnectionService } from './services/reconnection.service';
import { QueueMonitorService } from './services/queue-monitor.service';
import { MetricsService } from './services/metrics.service';
import { MonitoringService } from './services/monitoring.service';
import { AppWebSocketGateway } from './gateway/websocket.gateway';

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
    JwtModule.registerAsync({
      useFactory: (configService: ConfigService) => ({
        secret: configService.get('JWT_SECRET'),
        signOptions: { expiresIn: '1d' },
      }),
      inject: [ConfigService],
    }),
  ],
  controllers: [HealthController],
  providers: [
    AppService,
    MessageQueueService,
    ConnectionPoolService,
    BroadcastService,
    ClientStateService,
    ReconnectionService,
    QueueMonitorService,
    MetricsService,
    MonitoringService,
    AppWebSocketGateway,
  ],
  exports: [
    AppService,
    MessageQueueService,
    ConnectionPoolService,
    BroadcastService,
    ClientStateService,
    ReconnectionService,
    QueueMonitorService,
    MetricsService,
    MonitoringService,
  ]
})
export class AppModule {}
