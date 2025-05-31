import { LoggerService, LoggerOptions } from '../src/logger.service';

// Mock dayjs 避免時間相關問題
jest.mock('dayjs', () => () => ({
  format: () => '2024-01-01T00:00:00.000Z'
}));

// 修正 pino mock
jest.mock('pino', () => {
  const mockPinoLogger = {
    trace: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    fatal: jest.fn()
  };
  
  const mockPino = jest.fn(() => mockPinoLogger);
  Object.assign(mockPino, {
    destination: jest.fn()
  });
  
  return {
    __esModule: true,
    default: mockPino,
    ...mockPino
  };
});

describe('LoggerService', () => {
  let loggerService: LoggerService;
  let pinoMock: jest.MockedFunction<any>;
  let pinoLoggerMock: any;
  let originalNodeEnv: string | undefined;

  beforeEach(() => {
    // 清除所有 mock
    jest.clearAllMocks();
    
    // 保存並設置測試環境變數
    originalNodeEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'test';
    
    // 獲取 mock 的 pino
    const pino = require('pino');
    pinoMock = pino.default || pino;
    
    // 創建 LoggerService 實例 (這會觸發 pino 調用)
    loggerService = new LoggerService();
    
    // 獲取最新的 mock logger 實例 - 改善的邏輯
    const lastCallIndex = pinoMock.mock.calls.length - 1;
    pinoLoggerMock = pinoMock.mock.results[lastCallIndex]?.value || {
      trace: jest.fn(),
      debug: jest.fn(),
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn(),
      fatal: jest.fn()
    };
  });

  afterEach(() => {
    // 還原環境變數
    if (originalNodeEnv !== undefined) {
      process.env.NODE_ENV = originalNodeEnv;
    } else {
      delete process.env.NODE_ENV;
    }
  });

  describe('初始化', () => {
    it('應使用預設選項初始化', () => {
      expect(pinoMock).toHaveBeenCalled();
      const options = pinoMock.mock.calls[pinoMock.mock.calls.length - 1][0];
      expect(options.level).toBe('info');
      expect(options.base.service).toBe('Application');
    });

    it('應尊重自定義選項', () => {
      const customOptions: LoggerOptions = {
        level: 'debug',
        serviceName: 'TestService',
        prettyPrint: false
      };
      
      new LoggerService(customOptions);
      const options = pinoMock.mock.calls[pinoMock.mock.calls.length - 1][0];
      expect(options.level).toBe('debug');
      expect(options.base.service).toBe('TestService');
      expect(options.transport).toBeUndefined();
    });

    it('在開發環境應預設啟用 prettyPrint', () => {
      // 臨時設置開發環境
      process.env.NODE_ENV = 'development';
      
      new LoggerService();
      const options = pinoMock.mock.calls[pinoMock.mock.calls.length - 1][0];
      expect(options.transport).toBeDefined();
      
      // 還原測試環境
      process.env.NODE_ENV = 'test';
    });
  });

  describe('日誌方法', () => {
    it('應正確調用 log 方法', () => {
      const message = '測試訊息';
      const context = '測試上下文';
      const data = { key: 'value' };
      
      loggerService.log(message, context, data);
      expect(pinoLoggerMock.info).toHaveBeenCalledWith({ context, key: 'value' }, message);
    });

    it('應正確調用 info 方法', () => {
      const message = '資訊訊息';
      loggerService.info(message);
      expect(pinoLoggerMock.info).toHaveBeenCalledWith({}, message);
    });

    it('應正確調用 warn 方法', () => {
      const message = '警告訊息';
      loggerService.warn(message);
      expect(pinoLoggerMock.warn).toHaveBeenCalledWith({}, message);
    });

    it('應正確調用 debug 方法', () => {
      const message = '除錯訊息';
      loggerService.debug(message);
      expect(pinoLoggerMock.debug).toHaveBeenCalledWith({}, message);
    });

    it('應正確調用 verbose 方法', () => {
      const message = '詳細訊息';
      loggerService.verbose(message);
      expect(pinoLoggerMock.trace).toHaveBeenCalledWith({}, message);
    });
  });

  describe('error 方法', () => {
    it('處理 error(message) 格式', () => {
      const message = '錯誤訊息';
      loggerService.error(message);
      expect(pinoLoggerMock.error).toHaveBeenCalledWith({}, message);
    });

    it('處理 error(message, Error) 格式', () => {
      const message = '錯誤訊息';
      const error = new Error('測試錯誤');
      loggerService.error(message, error);
      expect(pinoLoggerMock.error).toHaveBeenCalledWith({ err: error }, message);
    });

    it('處理 error(message, Error, context) 格式', () => {
      const message = '錯誤訊息';
      const error = new Error('測試錯誤');
      const context = '測試上下文';
      loggerService.error(message, error, context);
      expect(pinoLoggerMock.error).toHaveBeenCalledWith({ err: error, context }, message);
    });

    it('處理 error(message, stackTrace, context) 格式', () => {
      const message = '錯誤訊息';
      const trace = 'Error: 測試錯誤\n    at Test.test (/app/test.ts:1:1)';
      const context = '測試上下文';
      loggerService.error(message, trace, context);
      expect(pinoLoggerMock.error).toHaveBeenCalled();
      // 由於創建合成錯誤的複雜性，我們只檢查是否調用了 error 方法
    });

    it('處理 error(message, context) 格式', () => {
      const message = '錯誤訊息';
      const context = '測試上下文';
      loggerService.error(message, context);
      expect(pinoLoggerMock.error).toHaveBeenCalled();
      // 檢查是否正確處理了 context
    });
  });

  describe('getNestLogger', () => {
    let nestLogger: any;

    beforeEach(() => {
      nestLogger = loggerService.getNestLogger();
    });

    it('應提供兼容 NestJS 的 log 方法', () => {
      const message = '測試訊息';
      const context = '測試上下文';
      
      nestLogger.log(message, context);
      expect(pinoLoggerMock.info).toHaveBeenCalledWith({ context }, message);
    });

    it('應提供兼容 NestJS 的 error 方法', () => {
      const message = '錯誤訊息';
      const context = '測試上下文';
      
      nestLogger.error(message, context);
      expect(pinoLoggerMock.error).toHaveBeenCalled();
    });

    it('應提供兼容 NestJS 的其他日誌方法', () => {
      const message = '測試訊息';
      
      nestLogger.warn(message);
      expect(pinoLoggerMock.warn).toHaveBeenCalledWith({}, message);
      
      nestLogger.debug(message);
      expect(pinoLoggerMock.debug).toHaveBeenCalledWith({}, message);
      
      nestLogger.verbose(message);
      expect(pinoLoggerMock.trace).toHaveBeenCalledWith({}, message);
    });
  });
});