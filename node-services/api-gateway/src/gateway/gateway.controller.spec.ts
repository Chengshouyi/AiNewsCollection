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
    const mockRequest = {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'host': 'localhost',
        'connection': 'keep-alive',
      },
      body: { test: 'data' },
    } as Request;

    const mockResponse = {
      setHeader: jest.fn(),
      status: jest.fn().mockReturnThis(),
      send: jest.fn(),
      json: jest.fn(),
    } as unknown as Response;

    it('應該成功轉發請求並返回響應', async () => {
      const mockRequest = {
        method: 'GET',
        headers: {
          'content-type': 'application/json',
          'host': 'localhost',
          'connection': 'keep-alive',
        },
        body: { test: 'data' },
      } as Request;

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
        mockRequest,
        mockResponse,
        { query: 'param' },
      );

      expect(mockHttpService.request).toHaveBeenCalledWith(expect.objectContaining({
        method: 'GET',
        url: 'http://python-backend/test-path',
        params: { query: 'param' },
        data: { test: 'data' },
        headers: expect.any(Object),
        validateStatus: expect.any(Function),
      }));

      expect(mockResponse.setHeader).toHaveBeenCalledWith('content-type', 'application/json');
      expect(mockResponse.status).toHaveBeenCalledWith(200);
      expect(mockResponse.send).toHaveBeenCalledWith({ message: 'success' });

      if (controller['shouldEmitWebSocketEvent']('test-path', mockRequest.method, mockBackendResponse.data)) {
        await controller['emitWebSocketEvent']('test-path', mockRequest.method, mockBackendResponse.data);
      }
    });

    it('應該處理後端錯誤響應', async () => {
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
        mockRequest,
        mockResponse,
        {},
      );

      expect(mockResponse.status).toHaveBeenCalledWith(404);
      expect(mockResponse.send).toHaveBeenCalledWith({ message: 'Not Found' });
    });

    it('應該處理後端超時錯誤', async () => {
      const mockTimeoutError = {
        request: {},
      };

      mockHttpService.request.mockReturnValue(throwError(() => mockTimeoutError));

      await controller.handleAllRequests(
        'test-path',
        mockRequest,
        mockResponse,
        {},
      );

      expect(mockResponse.status).toHaveBeenCalledWith(504);
      expect(mockResponse.json).toHaveBeenCalledWith({
        statusCode: 504,
        message: 'Gateway Timeout: No response from upstream server.',
        error: 'Gateway Timeout',
      });
    });

    it('應該處理其他錯誤', async () => {
      const mockError = new Error('Unknown error');

      mockHttpService.request.mockReturnValue(throwError(() => mockError));

      await controller.handleAllRequests(
        'test-path',
        mockRequest,
        mockResponse,
        {},
      );

      expect(mockResponse.status).toHaveBeenCalledWith(502);
      expect(mockResponse.json).toHaveBeenCalledWith({
        statusCode: 502,
        message: 'Bad Gateway: Error in setting up proxy request.',
        error: 'Bad Gateway',
      });
    });

    it('應該在任務完成時發送 WebSocket 通知', async () => {
      const mockTaskResponse = {
        status: 200,
        data: {
          success: true,
          data: {
            task_id: '123',
          },
          status: 'COMPLETED',
          progress: 100,
          message: '任務已完成',
        },
        headers: {
          'content-type': 'application/json',
        },
      };

      mockHttpService.request.mockReturnValue(of(mockTaskResponse));
      mockWebsocketClient.emit.mockReturnValue(of({}));

      // 添加更多日誌
      console.log('Debug info before handleAllRequests:', {
        mockTaskResponse,
        mockRequest,
      });

      await controller.handleAllRequests(
        'tasks/create',
        mockRequest,
        mockResponse,
        {},
      );

      // 添加更多日誌
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
    });
  });
});
