import { Controller, Get, Logger } from '@nestjs/common';
import { HealthCheck, HealthCheckService, HealthIndicatorResult, HealthCheckResult, HttpHealthIndicator } from '@nestjs/terminus';
import { RedisService } from '../shared/redis/redis.service';
import { LoggerService } from '@app/logger';
@Controller('health')
export class HealthController {

  constructor(
    private health: HealthCheckService,
    private http: HttpHealthIndicator,
    private redisService: RedisService,
    private logger: LoggerService
  ) {}

  @Get()
  @HealthCheck()
  check(): Promise<HealthCheckResult> {
    this.logger.log('check_health');
    return this.health.check([
      () => this.http.pingCheck('nestjs-docs', 'https://docs.nestjs.com'),
      async () => {
        try {
          await this.redisService.getClient().ping();
          this.logger.log('redis_ping_success', HealthController.name);
          return { redis: { status: 'up' } };
        } catch (error) {
          this.logger.error('redis_ping_failed', error, HealthController.name);
          return { redis: { status: 'down', message: error.message } };
        }
      }
    ]);
  }
}
