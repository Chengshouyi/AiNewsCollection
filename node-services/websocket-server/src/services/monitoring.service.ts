import { Injectable } from '@nestjs/common';
import { MetricsService } from './metrics.service';
import { QueueMonitorService } from './queue-monitor.service';
import { LoggerService } from '@app/logger';

@Injectable()
export class MonitoringService {
  private readonly monitoringInterval = 60000; // 每分鐘記錄一次
  private intervalRef: NodeJS.Timeout;

  constructor(
    private readonly metrics: MetricsService,
    private readonly queueMonitor: QueueMonitorService,
    private readonly logger: LoggerService,
  ) {
    this.startMonitoring();
  }

  getMonitoringInterval(): number {
    return this.monitoringInterval;
  }

  private startMonitoring() {
    this.intervalRef = setInterval(() => {
      try {
        const metrics = this.metrics.getMetrics();
        const queueMetrics = this.queueMonitor.getMetrics();
        
        this.logger.log('系統指標', 'MonitoringService', {
          ...metrics,
          ...queueMetrics,
          timestamp: new Date(),
        });
      } catch (error) {
        this.logger.error(
          '收集系統指標時發生錯誤', 
          error instanceof Error ? error : new Error(String(error)), 
          'MonitoringService'
        );
      }
    }, this.monitoringInterval);
  }

  // 用於測試和系統關閉時清理資源
  stopMonitoring() {
    if (this.intervalRef) {
      clearInterval(this.intervalRef);
    }
  }
}
