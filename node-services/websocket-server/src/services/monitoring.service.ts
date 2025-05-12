import { Injectable } from '@nestjs/common';
import { MetricsService } from './metrics.service';
import { QueueMonitorService } from './queue-monitor.service';
import { LoggerService } from '@app/logger';

@Injectable()
export class MonitoringService {
  constructor(
    private readonly metrics: MetricsService,
    private readonly queueMonitor: QueueMonitorService,
    private readonly logger: LoggerService,
  ) {
    this.startMonitoring();
  }

  private startMonitoring() {
    setInterval(() => {
      const metrics = this.metrics.getMetrics();
      const queueMetrics = this.queueMonitor.getMetrics();
      
      this.logger.log('系統指標', 'MonitoringService', {
        ...metrics,
        ...queueMetrics,
        timestamp: new Date(),
      });
    }, 60000); // 每分鐘記錄一次
  }
}
