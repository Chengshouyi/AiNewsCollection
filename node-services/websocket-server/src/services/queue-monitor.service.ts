import { Injectable } from '@nestjs/common';

@Injectable()
export class QueueMonitorService {
  private readonly metrics = {
    messagesProcessed: 0,
    messagesFailed: 0,
    averageProcessingTime: 0,
  };

  recordMessageProcessed(processingTime: number) {
    this.metrics.messagesProcessed++;
    this.updateAverageProcessingTime(processingTime);
  }

  recordMessageFailed() {
    this.metrics.messagesFailed++;
  }

  getMetrics() {
    return { ...this.metrics };
  }

  private updateAverageProcessingTime(processingTime: number) {
    this.metrics.averageProcessingTime = 
      (this.metrics.averageProcessingTime + processingTime) / 2;
  }
}
