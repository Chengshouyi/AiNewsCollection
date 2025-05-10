import { Controller, Get, Logger } from '@nestjs/common';
import { HealthCheck, HealthCheckService, HealthIndicatorResult, HealthCheckResult, HttpHealthIndicator } from '@nestjs/terminus';
import { RedisService } from '../shared/redis/redis.service';

@Controller('health')
export class HealthController {
  private readonly logger = new Logger(HealthController.name);

  constructor(
    private health: HealthCheckService,
    private http: HttpHealthIndicator,
    private redisService: RedisService
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
          return { redis: { status: 'up' } };
        } catch (error) {
          return { redis: { status: 'down', message: error.message } };
        }
      }
    ]);
  }
}
