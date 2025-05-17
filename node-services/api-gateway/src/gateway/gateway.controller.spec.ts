import { Test, TestingModule } from '@nestjs/testing';
import { GatewayController } from './gateway.controller';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { ClientProxy } from '@nestjs/microservices';
import { LoggerService } from '@app/logger';
import { Request, Response } from 'express';
import { of, throwError } from 'rxjs';

describe('GatewayController', () => {
  let controller: GatewayController;
  let httpService: HttpService;
  let configService: ConfigService;
  let websocketClient: ClientProxy;
  let loggerService: LoggerService;

  const mockHttpService = {
    request: jest.fn(),
  };

  const mockConfigService = {
    get: jest.fn().mockImplementation((key: string) => {
      if (key === 'PYTHON_BACKEND_URL') return 'http://python-backend';
      return null;
    }),
  };

  const mockWebsocketClient = {
    emit: jest.fn(),
  };

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

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [GatewayController],
      providers: [
        {
          provide: HttpService,
          useValue: mockHttpService,
        },
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: 'WEBSOCKET_SERVICE',
          useValue: mockWebsocketClient,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    controller = module.get<GatewayController>(GatewayController);
    httpService = module.get<HttpService>(HttpService);
    configService = module.get<ConfigService>(ConfigService);
    websocketClient = module.get<ClientProxy>('WEBSOCKET_SERVICE');
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });

  describe('handleAllRequests', () => {
    const mockRequestBase = {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        host: 'localhost',
        connection: 'keep-alive',
      },
      body: { test: 'data' },
      ip: '127.0.0.1',
      protocol: 'http',
      get: jest.fn(function(headerName: string) {
        const lowerCaseHeaderName = headerName.toLowerCase();
        if (this.headers && this.headers[lowerCaseHeaderName]) {
          return this.headers[lowerCaseHeaderName];
        }
        return undefined;
      }),
    };

    const mockResponse = {
      setHeader: jest.fn(),
      status: jest.fn().mockReturnThis(),
      send: jest.fn(),
      json: jest.fn(),
    } as unknown as Response;

    beforeEach(() => {
      jest.clearAllMocks();
      
      mockConfigService.get.mockImplementation((key: string) => {
        if (key === 'PYTHON_BACKEND_URL') return 'http://python-backend';
        return null;
      });
      mockLoggerService.log.mockImplementation((message: any, context?: string) => {
        console.log(`[TEST LOG] ${context ? '[' + context + '] ' : ''}${message}`);
      });
      mockLoggerService.error.mockImplementation((message: any, trace?: string, context?: string) => {
        console.error(`[TEST ERROR] ${context ? '[' + context + '] ' : ''}${message}${trace ? '\n' + trace : ''}`);
      });

      mockRequestBase.get.mockClear();
      mockRequestBase.get.mockImplementation(function(headerName: string) {
        const lowerCaseHeaderName = headerName.toLowerCase();
        if (this.headers && this.headers[lowerCaseHeaderName]) {
          return this.headers[lowerCaseHeaderName];
        }
        return undefined;
      });
    });

    it('應該成功轉發請求並返回響應', async () => {
      const currentTestMockRequest = {
        ...mockRequestBase,
        method: 'GET',
        headers: {
          ...mockRequestBase.headers,
          'content-type': 'application/json',
          host: 'testhost.com',
        },
        body: { test: 'data' },
      } as unknown as Request;
      
      const mockBackendResponse = {
        status: 200,
        data: { message: 'success' },
        headers: {
          'content-type': 'application/json',
        },
      };

      mockHttpService.request.mockReturnValue(of(mockBackendResponse));

      await controller.handleAllRequests(
        'test-path',
        currentTestMockRequest,
        mockResponse,
        { query: 'param' },
      );

      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        method: 'GET',
        url: 'http://python-backend/test-path',
        params: { query: 'param' },
        data: { test: 'data' },
        headers: expect.objectContaining({
          'x-forwarded-host': 'testhost.com',
          'x-forwarded-for': currentTestMockRequest.ip,
          'x-forwarded-proto': currentTestMockRequest.protocol,
        }),
        validateStatus: expect.any(Function),
      }));

      expect(mockResponse.setHeader).toHaveBeenCalledWith('content-type', 'application/json');
      expect(mockResponse.status).toHaveBeenCalledWith(200);
      expect(mockResponse.send).toHaveBeenCalledWith({ message: 'success' });

      if (controller['shouldEmitWebSocketEvent']('test-path', currentTestMockRequest.method, mockBackendResponse.data)) {
        await controller['emitWebSocketEvent']('test-path', currentTestMockRequest.method, mockBackendResponse.data);
      }
    });

    it('應該處理後端錯誤響應', async () => {
      const currentTestMockRequest = {
        ...mockRequestBase,
        method: 'POST',
        headers: {
          ...mockRequestBase.headers,
          host: 'anotherhost.com',
        },
      } as unknown as Request;

      const mockErrorResponse = {
        response: {
          status: 404,
          data: { message: 'Not Found' },
          headers: {
            'content-type': 'application/json',
          },
        },
      };

      mockHttpService.request.mockReturnValue(throwError(() => mockErrorResponse));

      await controller.handleAllRequests(
        'test-path',
        currentTestMockRequest,
        mockResponse,
        {},
      );

      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        headers: expect.objectContaining({
          'x-forwarded-host': 'anotherhost.com',
        }),
      }));

      expect(mockResponse.status).toHaveBeenCalledWith(404);
      expect(mockResponse.send).toHaveBeenCalledWith({ message: 'Not Found' });
    });

    it('應該處理後端超時錯誤', async () => {
      const currentTestMockRequest = {
        ...mockRequestBase,
        headers: { ...mockRequestBase.headers, host: 'timeout-host.com' },
      } as unknown as Request;
    
      const mockTimeoutError = {
        request: {},
      };
    
      mockHttpService.request.mockReturnValue(throwError(() => mockTimeoutError));
    
      await controller.handleAllRequests(
        'test-path',
        currentTestMockRequest,
        mockResponse,
        {},
      );
    
      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        headers: expect.objectContaining({ 'x-forwarded-host': 'timeout-host.com' }),
      }));
      expect(mockResponse.status).toHaveBeenCalledWith(504);
      expect(mockResponse.json).toHaveBeenCalledWith({
        statusCode: 504,
        message: 'Gateway Timeout: No response from upstream server.',
        error: 'Gateway Timeout',
      });
    });
    
    it('應該處理其他錯誤', async () => {
      const currentTestMockRequest = {
        ...mockRequestBase,
        headers: { ...mockRequestBase.headers, host: 'other-error-host.com' },
      } as unknown as Request;

      const mockError = new Error('Unknown error');
    
      mockHttpService.request.mockReturnValue(throwError(() => mockError));
    
      await controller.handleAllRequests(
        'test-path',
        currentTestMockRequest,
        mockResponse,
        {},
      );
    
      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        headers: expect.objectContaining({ 'x-forwarded-host': 'other-error-host.com' }),
      }));
      expect(mockResponse.status).toHaveBeenCalledWith(502);
      expect(mockResponse.json).toHaveBeenCalledWith({
        statusCode: 502,
        message: 'Bad Gateway: Error in setting up proxy request.',
        error: 'Bad Gateway',
      });
    });
    
    it('應該在任務完成時發送 WebSocket 通知', async () => {
      const currentTestMockRequest = {
        ...mockRequestBase,
        method: 'POST',
        headers: { 
          ...mockRequestBase.headers, 
          'content-type': 'application/json',
          host: 'task-host.com',
        },
        body: { test: 'data' },
      } as unknown as Request;

      const mockTaskResponse = {
        status: 200,
        data: {
          success: true,
          data: { task_id: '123' },
          status: 'COMPLETED',
          progress: 100,
          message: '任務已完成',
        },
        headers: { 'content-type': 'application/json' },
      };
    
      mockHttpService.request.mockReturnValue(of(mockTaskResponse));
      mockWebsocketClient.emit.mockReturnValue(of({}));
    
      console.log('Debug info before handleAllRequests:', {
        mockTaskResponse,
        mockRequest: currentTestMockRequest,
      });
    
      await controller.handleAllRequests(
        'tasks/create',
        currentTestMockRequest,
        mockResponse,
        {},
      );
      
      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        headers: expect.objectContaining({ 'x-forwarded-host': 'task-host.com' }),
      }));
    
      console.log('Debug info after handleAllRequests:', {
        emitCalls: mockWebsocketClient.emit.mock.calls,
      });
    
      expect(mockWebsocketClient.emit).toHaveBeenCalledWith('task_progress', {
        room: 'task_123',
        event: 'task_progress',
        data: {
          task_id: '123',
          status: 'COMPLETED',
          progress: 100,
          message: '任務已完成',
          timestamp: expect.any(Date),
        },
      });
      expect(mockResponse.status).toHaveBeenCalledWith(200);
      expect(mockResponse.send).toHaveBeenCalledWith(mockTaskResponse.data);
    });
  });
});
