import { Test, TestingModule } from '@nestjs/testing';
import { ErrorHandlerMiddleware } from './error-handler.middleware';
import { LoggerService } from '@app/logger';
import { Request, Response } from 'express';

describe('ErrorHandlerMiddleware', () => {
  let middleware: ErrorHandlerMiddleware;
  let loggerService: LoggerService;

  const mockLoggerService = {
    log: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(`[TEST LOG] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    error: jest.fn().mockImplementation((message: any, trace?: string, context?: string) => {
      console.error(`[TEST ERROR] ${context ? '[' + context + '] ' : ''}${message}${trace ? '\n' + trace : ''}`);
    }),
    warn: jest.fn().mockImplementation((message: any, context?: string) => {
      console.warn(`[TEST WARN] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    debug: jest.fn().mockImplementation((message: any, context?: string) => {
      console.debug(`[TEST DEBUG] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
    verbose: jest.fn().mockImplementation((message: any, context?: string) => {
      console.log(`[TEST VERBOSE] ${context ? '[' + context + '] ' : ''}${message}`);
    }),
  };

  const mockRequest = {} as Request;
  const mockResponse = {
    status: jest.fn().mockReturnThis(),
    json: jest.fn(),
  } as unknown as Response;
  const mockNext = jest.fn();

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ErrorHandlerMiddleware,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    middleware = module.get<ErrorHandlerMiddleware>(ErrorHandlerMiddleware);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(middleware).toBeDefined();
  });

  describe('use', () => {
    it('當沒有錯誤時應該正常執行 next()', () => {
      middleware.use(mockRequest, mockResponse, mockNext);
      
      expect(mockNext).toHaveBeenCalled();
      expect(mockLoggerService.error).not.toHaveBeenCalled();
      expect(mockResponse.status).not.toHaveBeenCalled();
      expect(mockResponse.json).not.toHaveBeenCalled();
    });

    it('當發生錯誤時應該記錄錯誤並返回 500 狀態碼', () => {
      const error = new Error('測試錯誤');
      mockNext.mockImplementationOnce(() => {
        throw error;
      });

      middleware.use(mockRequest, mockResponse, mockNext);
      
      expect(mockLoggerService.error).toHaveBeenCalledWith('WebSocket 錯誤', error);
      expect(mockResponse.status).toHaveBeenCalledWith(500);
      expect(mockResponse.json).toHaveBeenCalledWith({
        statusCode: 500,
        message: '內部伺服器錯誤',
        error: error.message,
      });
    });
  });
}); 