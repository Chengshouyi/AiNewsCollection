@Injectable()
export class MetricsService {
  private readonly metrics = {
    activeConnections: 0,
    messagesPerSecond: 0,
    averageLatency: 0,
    errorRate: 0,
  };

  recordConnection() {
    this.metrics.activeConnections++;
  }

  recordDisconnection() {
    this.metrics.activeConnections--;
  }

  recordMessageLatency(latency: number) {
    this.metrics.averageLatency = 
      (this.metrics.averageLatency + latency) / 2;
  }

  getMetrics() {
    return { ...this.metrics };
  }
}
