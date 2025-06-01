import { QueueMonitorService } from './queue-monitor.service';

describe('QueueMonitorService', () => {
  let service: QueueMonitorService;

  beforeEach(() => {
    service = new QueueMonitorService();
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('recordMessageProcessed', () => {
    it('應該遞增 messagesProcessed 並更新平均處理時間', () => {
      service.recordMessageProcessed(100);
      let metrics = service.getMetrics();
      expect(metrics.messagesProcessed).toBe(1);
      expect(metrics.averageProcessingTime).toBe(50); // (0+100)/2

      service.recordMessageProcessed(200);
      metrics = service.getMetrics();
      expect(metrics.messagesProcessed).toBe(2);
      expect(metrics.averageProcessingTime).toBe(125); // (50+200)/2
    });
  });

  describe('recordMessageFailed', () => {
    it('應該遞增 messagesFailed', () => {
      service.recordMessageFailed();
      let metrics = service.getMetrics();
      expect(metrics.messagesFailed).toBe(1);
      service.recordMessageFailed();
      metrics = service.getMetrics();
      expect(metrics.messagesFailed).toBe(2);
    });
  });

  describe('getMetrics', () => {
    it('應該回傳 metrics 的複本', () => {
      service.recordMessageProcessed(100);
      service.recordMessageFailed();
      const metrics = service.getMetrics();
      expect(metrics).toEqual({
        messagesProcessed: 1,
        messagesFailed: 1,
        averageProcessingTime: 50,
      });
      // 修改回傳值不應影響內部狀態
      metrics.messagesProcessed = 999;
      expect(service.getMetrics().messagesProcessed).toBe(1);
    });
  });
});
