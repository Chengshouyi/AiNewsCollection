import { Injectable } from '@nestjs/common';

@Injectable()
export class MetricsService {
  private readonly metrics = {
    activeConnections: 0,
    messagesPerSecond: 0,
    averageLatency: 0,
    errorRate: 0,
  };

  private latencyCount = 0;
  private totalLatency = 0;

  recordConnection() {
    this.metrics.activeConnections++;
  }

  recordDisconnection() {
    if (this.metrics.activeConnections > 0) {
      this.metrics.activeConnections--;
    }
  }

  recordMessageLatency(latency: number) {
    this.latencyCount++;
    this.totalLatency += latency;
    this.metrics.averageLatency = this.totalLatency / this.latencyCount;
  }

  getMetrics() {
    return { ...this.metrics };
  }
}
