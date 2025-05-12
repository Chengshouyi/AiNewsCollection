import { Test, TestingModule } from '@nestjs/testing';
import { JwtService } from '@nestjs/jwt';
import { WebSocketAuthGuard } from './websocket-auth.guard';
import { LoggerService } from '@app/logger';
import { ExecutionContext } from '@nestjs/common';
import { Socket } from 'socket.io';

describe('WebSocketAuthGuard', () => {
  let guard: WebSocketAuthGuard;
  let jwtService: JwtService;
  let loggerService: LoggerService;

  const mockJwtService = {
    verifyAsync: jest.fn(),
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

  const mockExecutionContext = {
    switchToWs: () => ({
      getClient: () => ({
        handshake: {
          auth: {
            token: 'test-token',
          },
        },
        data: {},
      } as unknown as Socket),
    }),
  } as ExecutionContext;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        WebSocketAuthGuard,
        {
          provide: JwtService,
          useValue: mockJwtService,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    guard = module.get<WebSocketAuthGuard>(WebSocketAuthGuard);
    jwtService = module.get<JwtService>(JwtService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(guard).toBeDefined();
  });

  describe('canActivate', () => {
    it('當 token 有效時應該返回 true', async () => {
      const mockPayload = { sub: '123', username: 'test' };
      mockJwtService.verifyAsync.mockResolvedValue(mockPayload);

      const result = await guard.canActivate(mockExecutionContext);
      
      expect(result).toBe(true);
      expect(mockJwtService.verifyAsync).toHaveBeenCalledWith('test-token');
    });

    it('當 token 無效時應該返回 false', async () => {
      mockJwtService.verifyAsync.mockRejectedValue(new Error('Invalid token'));

      const result = await guard.canActivate(mockExecutionContext);
      
      expect(result).toBe(false);
      expect(mockLoggerService.error).toHaveBeenCalledWith('認證失敗', expect.any(Error));
    });

    it('當沒有 token 時應該返回 false', async () => {
      const contextWithoutToken = {
        switchToWs: () => ({
          getClient: () => ({
            handshake: {
              auth: {},
            },
            data: {},
          } as Socket),
        }),
      } as ExecutionContext;

      const result = await guard.canActivate(contextWithoutToken);
      
      expect(result).toBe(false);
      expect(mockLoggerService.error).toHaveBeenCalled();
    });
  });
}); 