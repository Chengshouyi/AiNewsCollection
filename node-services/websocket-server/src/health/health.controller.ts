import { Controller, Get, Logger } from '@nestjs/common';
import { HealthCheck, HealthCheckService, HealthIndicatorResult, HealthCheckResult } from '@nestjs/terminus';
import { RedisHealthIndicator } from '@nestjs/terminus-redis';

@Controller('health')
export class HealthController {
  private readonly logger = new Logger(HealthController.name);

  constructor(
    private health: HealthCheckService,
    private redisIndicator: RedisHealthIndicator,
  ) {}

  @Get()
  @HealthCheck()
  check(): Promise<HealthCheckResult> {
    this.logger.log('check_health');
    return this.health.check([
      async () => this.redisIndicator.pingCheck('redis', { timeout: 1500 }),
    ]);
  }
}
