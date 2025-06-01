import { Test, TestingModule } from '@nestjs/testing';
import { MonitoringService } from './monitoring.service';
import { MetricsService } from './metrics.service';
import { QueueMonitorService } from './queue-monitor.service';
import { LoggerService } from '@app/logger';

describe('MonitoringService', () => {
  let service: MonitoringService;
  let metricsService: { getMetrics: jest.Mock };
  let queueMonitorService: { getMetrics: jest.Mock };
  let loggerService: {
    log: jest.Mock;
    error: jest.Mock;
    warn: jest.Mock;
    debug: jest.Mock;
    verbose: jest.Mock;
  };

  // originalSetInterval and originalClearInterval are kept due to existing beforeAll/afterAll
  // but their direct manipulation is generally superseded by Jest's timer and spy management.
  let originalSetInterval: typeof setInterval;
  let originalClearInterval: typeof clearInterval;

  // 模擬數據
  const mockMetrics = {
    activeConnections: 5,
    messagesPerSecond: 10,
    averageLatency: 50,
    errorRate: 0.01,
  };

  const mockQueueMetrics = {
    messagesProcessed: 100,
    messagesFailed: 2,
    averageProcessingTime: 30,
  };

  // 保存原始的計時器函數 (as per existing code)
  beforeAll(() => {
    originalSetInterval = global.setInterval;
    originalClearInterval = global.clearInterval;
  });

  beforeEach(async () => {
    jest.useFakeTimers(); // Use Jest's fake timers

    // Spy on global timer functions AFTER useFakeTimers
    // so we are spying on Jest's controlled versions.
    jest.spyOn(global, 'setInterval');
    jest.spyOn(global, 'clearInterval');

    // 創建模擬服務
    const metricsServiceMock = {
      getMetrics: jest.fn().mockReturnValue(mockMetrics),
    };

    const queueMonitorServiceMock = {
      getMetrics: jest.fn().mockReturnValue(mockQueueMetrics),
    };

    // Logger mock - ensuring all methods are jest.fn() for proper tracking
    const loggerServiceMock = {
      log: jest.fn(),
      error: jest.fn(),
      warn: jest.fn(),
      debug: jest.fn(),
      verbose: jest.fn(),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MonitoringService,
        {
          provide: MetricsService,
          useValue: metricsServiceMock,
        },
        {
          provide: QueueMonitorService,
          useValue: queueMonitorServiceMock,
        },
        {
          provide: LoggerService,
          useValue: loggerServiceMock,
        },
      ],
    }).compile();

    // Service instance is created AFTER jest.useFakeTimers() and jest.spyOn().
    service = module.get<MonitoringService>(MonitoringService);
    metricsService = module.get(MetricsService);
    queueMonitorService = module.get(QueueMonitorService);
    loggerService = module.get(LoggerService);
  });

  afterEach(() => {
    // Stop monitoring to clear any intervals set by the service itself.
    // This will use the spied clearInterval.
    service.stopMonitoring();

    // Clear all mocks (including spies on setInterval/clearInterval)
    jest.clearAllMocks();

    // Restore real timers
    jest.useRealTimers();
  });

  // 復原原始的計時器函數 (as per existing code)
  afterAll(() => {
    global.setInterval = originalSetInterval;
    global.clearInterval = originalClearInterval;
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('服務配置', () => {
    it('應該返回正確的監控間隔', () => {
      expect(service.getMonitoringInterval()).toBe(60000);
    });
  });

  describe('監控初始化', () => {
    it('應該在建構時啟動監控', () => {
      // global.setInterval is now a Jest spy
      expect(global.setInterval).toHaveBeenCalled();
      expect(global.setInterval).toHaveBeenCalledWith(
        expect.any(Function),
        60000,
      );
    });

    it('應該設置正確的監控時間間隔', () => {
      // global.setInterval is now a Jest spy
      expect(global.setInterval).toHaveBeenCalledWith(
        expect.any(Function),
        service.getMonitoringInterval(),
      );
    });
  });

  describe('監控停止', () => {
    it('應該能夠正確停止監控', () => {
      // stopMonitoring calls clearInterval internally
      service.stopMonitoring();

      // global.clearInterval is now a Jest spy
      expect(global.clearInterval).toHaveBeenCalled();

      // Advance timers to see if the callback would have been called
      jest.advanceTimersByTime(service.getMonitoringInterval());

      expect(metricsService.getMetrics).not.toHaveBeenCalled();
      expect(queueMonitorService.getMetrics).not.toHaveBeenCalled();
      expect(loggerService.log).not.toHaveBeenCalled();
    });
  });

  describe('監控執行', () => {
    it('應該每分鐘收集並記錄指標', () => {
      jest.advanceTimersByTime(service.getMonitoringInterval());

      expect(metricsService.getMetrics).toHaveBeenCalled();
      expect(queueMonitorService.getMetrics).toHaveBeenCalled();
      expect(loggerService.log).toHaveBeenCalledWith(
        '系統指標',
        'MonitoringService',
        expect.objectContaining({
          ...mockMetrics,
          ...mockQueueMetrics,
          timestamp: expect.any(Date) as Date,
        }),
      );
    });

    it('應該多次記錄指標', () => {
      jest.advanceTimersByTime(service.getMonitoringInterval() * 3);

      expect(metricsService.getMetrics).toHaveBeenCalledTimes(3);
      expect(queueMonitorService.getMetrics).toHaveBeenCalledTimes(3);
      expect(loggerService.log).toHaveBeenCalledTimes(3);
    });

    it('應該在指標變化時仍然正確記錄', () => {
      jest.advanceTimersByTime(service.getMonitoringInterval()); // First call

      const newMetrics = {
        activeConnections: 10,
        messagesPerSecond: 20,
        averageLatency: 60,
        errorRate: 0.02,
      };
      const newQueueMetrics = {
        messagesProcessed: 200,
        messagesFailed: 4,
        averageProcessingTime: 35,
      };

      metricsService.getMetrics.mockReturnValue(newMetrics);
      queueMonitorService.getMetrics.mockReturnValue(newQueueMetrics);

      jest.advanceTimersByTime(service.getMonitoringInterval()); // Second call

      expect(loggerService.log).toHaveBeenNthCalledWith(
        2, // Second call to logger.log
        '系統指標',
        'MonitoringService',
        expect.objectContaining({
          ...newMetrics,
          ...newQueueMetrics,
          timestamp: expect.any(Date) as Date,
        }),
      );
    });
  });

  describe('數據整合', () => {
    it('應該正確合併指標數據', () => {
      jest.advanceTimersByTime(service.getMonitoringInterval());
      const loggedData = loggerService.log.mock.calls[0][2] as Record<
        string,
        unknown
      >;

      expect(loggedData).toMatchObject({
        activeConnections: mockMetrics.activeConnections,
        messagesPerSecond: mockMetrics.messagesPerSecond,
        averageLatency: mockMetrics.averageLatency,
        errorRate: mockMetrics.errorRate,
        messagesProcessed: mockQueueMetrics.messagesProcessed,
        messagesFailed: mockQueueMetrics.messagesFailed,
        averageProcessingTime: mockQueueMetrics.averageProcessingTime,
      });
    });

    it('應該包含正確的時間戳', () => {
      const beforeTime = new Date().getTime();
      jest.advanceTimersByTime(service.getMonitoringInterval());

      const loggedData = loggerService.log.mock.calls[0][2] as Record<
        string,
        unknown
      >;
      expect(loggedData.timestamp).toBeInstanceOf(Date);

      const loggedTimestamp = (loggedData.timestamp as Date).getTime();
      // Check if the logged timestamp is within a reasonable range of when the timer fired
      // Allow for a small delta due to test execution, and fake timer precision.
      // This test is slightly more robust than comparing to `new Date()` directly after advancing time.
      expect(loggedTimestamp).toBeGreaterThanOrEqual(beforeTime);
      // Advancing by 60000ms doesn't mean the system clock also advanced exactly that for `new Date()`.
      // We are checking the `new Date()` *inside* the `setInterval` callback.
      // The important part is that it's a Date object.
      // The previous check `Math.abs(now.getTime() - timestamp.getTime())).toBeLessThan(1000)`
      // might be flaky depending on how fake timers handle `new Date()`.
      // For fake timers, `new Date()` inside a callback fired by `advanceTimersByTime`
      // should reflect the "advanced" time.
      const dateNowInFakeTimer = new Date(Date.now()); // Date.now() should be mocked by fake timers
      expect(
        Math.abs(dateNowInFakeTimer.getTime() - loggedTimestamp),
      ).toBeLessThan(1000);
    });

    it('應該使用正確的日誌類別', () => {
      jest.advanceTimersByTime(service.getMonitoringInterval());
      expect(loggerService.log).toHaveBeenCalledWith(
        '系統指標',
        'MonitoringService',
        expect.any(Object),
      );
    });
  });

  describe('錯誤處理', () => {
    it('應該處理指標服務拋出異常的情況', () => {
      const testError = new Error('測試錯誤');
      metricsService.getMetrics.mockImplementation(() => {
        throw testError;
      });

      jest.advanceTimersByTime(service.getMonitoringInterval());

      expect(loggerService.error).toHaveBeenCalledWith(
        '收集系統指標時發生錯誤',
        testError,
        'MonitoringService',
      );
      expect(loggerService.log).not.toHaveBeenCalled();
    });

    it('應該處理隊列監控服務拋出異常的情況', () => {
      const testError = new Error('隊列監控錯誤');
      queueMonitorService.getMetrics.mockImplementation(() => {
        throw testError;
      });

      jest.advanceTimersByTime(service.getMonitoringInterval());

      expect(loggerService.error).toHaveBeenCalledWith(
        '收集系統指標時發生錯誤',
        testError,
        'MonitoringService',
      );
      expect(loggerService.log).not.toHaveBeenCalled();
    });

    it('應該處理非 Error 類型的異常', () => {
      const nonErrorObject = '字串類型錯誤';
      metricsService.getMetrics.mockImplementation(() => {
        throw nonErrorObject;
      });

      jest.advanceTimersByTime(service.getMonitoringInterval());

      expect(loggerService.error).toHaveBeenCalledWith(
        '收集系統指標時發生錯誤',
        expect.any(Error), // The service wraps non-Errors
        'MonitoringService',
      );

      const errorCaughtByLogger = loggerService.error.mock.calls[0][1] as Error;
      expect(errorCaughtByLogger.message).toBe(String(nonErrorObject));
      expect(loggerService.log).not.toHaveBeenCalled();
    });
  });
});
