import { Test, TestingModule } from '@nestjs/testing';
import { MetricsService } from './metrics.service';

describe('MetricsService', () => {
  let service: MetricsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [MetricsService],
    }).compile();

    service = module.get<MetricsService>(MetricsService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('連接計數管理', () => {
    it('應該正確記錄新連接', () => {
      service.recordConnection();
      const metrics = service.getMetrics();
      expect(metrics.activeConnections).toBe(1);
    });

    it('應該正確記錄多個連接', () => {
      service.recordConnection();
      service.recordConnection();
      service.recordConnection();
      const metrics = service.getMetrics();
      expect(metrics.activeConnections).toBe(3);
    });

    it('應該正確記錄斷開連接', () => {
      service.recordConnection();
      service.recordConnection();
      service.recordDisconnection();
      const metrics = service.getMetrics();
      expect(metrics.activeConnections).toBe(1);
    });

    it('不應該讓連接數變成負數', () => {
      service.recordDisconnection();
      service.recordDisconnection();
      const metrics = service.getMetrics();
      expect(metrics.activeConnections).toBe(0);
    });
  });

  describe('延遲時間記錄', () => {
    it('應該正確計算平均延遲時間', () => {
      service.recordMessageLatency(100);
      service.recordMessageLatency(200);
      const metrics = service.getMetrics();
      expect(metrics.averageLatency).toBe(150);
    });

    it('應該正確處理單一延遲記錄', () => {
      service.recordMessageLatency(100);
      const metrics = service.getMetrics();
      expect(metrics.averageLatency).toBe(100);
    });

    it('應該正確處理零延遲', () => {
      service.recordMessageLatency(0);
      const metrics = service.getMetrics();
      expect(metrics.averageLatency).toBe(0);
    });
  });

  describe('指標獲取', () => {
    it('應該返回所有指標的副本', () => {
      const initialMetrics = service.getMetrics();
      expect(initialMetrics).toEqual({
        activeConnections: 0,
        messagesPerSecond: 0,
        averageLatency: 0,
        errorRate: 0,
      });

      // 修改指標
      service.recordConnection();
      service.recordMessageLatency(100);

      // 確認原始指標物件未被修改
      expect(initialMetrics).toEqual({
        activeConnections: 0,
        messagesPerSecond: 0,
        averageLatency: 0,
        errorRate: 0,
      });

      // 確認新的指標值
      const updatedMetrics = service.getMetrics();
      expect(updatedMetrics).toEqual({
        activeConnections: 1,
        messagesPerSecond: 0,
        averageLatency: 100,
        errorRate: 0,
      });
    });
  });
}); 