import { Test, TestingModule } from '@nestjs/testing';
import { ApiGatewayWebSocket } from './websocket.gateway';
import { ConfigService } from '@nestjs/config';
import { Namespace } from 'socket.io'; // Server type is from socket.io Namespace
import { io, Socket as ClientSocket } from 'socket.io-client'; // Use ClientSocket alias for clarity
import { Server as HttpServer } from 'http';
import { INestApplication } from '@nestjs/common';
import { IoAdapter } from '@nestjs/platform-socket.io';
import { LoggerService } from '@app/logger';

// 設置更長的超時時間
jest.setTimeout(20000);

describe('ApiGatewayWebSocket', () => {
  let app: INestApplication;
  let gateway: ApiGatewayWebSocket;
  let httpServer: HttpServer;
  let clientSocket: ClientSocket; // Use aliased type
  let welcomeMessageReceived: any = null;

  const mockConfigService = {
    get: jest.fn().mockImplementation((key: string) => {
      if (key === 'WEBSOCKET_HEARTBEAT_INTERVAL') return 30000;
      return null;
    }),
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
    console.log('開始設置測試環境...');
    welcomeMessageReceived = null;
    
    const moduleFixture: TestingModule = await Test.createTestingModule({
      providers: [
        ApiGatewayWebSocket,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    console.log('測試模組已創建');

    app = moduleFixture.createNestApplication();
    app.useWebSocketAdapter(new IoAdapter(app));
    await app.init();

    httpServer = app.getHttpServer();
    gateway = moduleFixture.get<ApiGatewayWebSocket>(ApiGatewayWebSocket);
    
    console.log('啟動 NestJS 應用監聽...');
    await app.listen(0);
    const address = httpServer.address();
    const port = typeof address === 'string' ? parseInt(address.split(':')[1], 10) : address?.port;
    if (!port) {
      throw new Error('無法獲取服務器端口');
    }
    console.log(`服務器監聽在端口 ${port}`);

    console.log('等待客戶端連接並接收歡迎訊息...');
    
    await new Promise<void>((resolve, reject) => {
      const WELCOME_EVENT = 'welcome'; // Define event name
      let connectTimeoutId: NodeJS.Timeout;
      let welcomeListener: (...args: any[]) => void;

      const cleanupTimeoutsAndListeners = () => {
        if (connectTimeoutId) clearTimeout(connectTimeoutId);
        if (welcomeListener && clientSocket) clientSocket.off(WELCOME_EVENT, welcomeListener);
      };

      connectTimeoutId = setTimeout(() => {
        cleanupTimeoutsAndListeners();
        reject(new Error('客戶端連接或等待歡迎訊息超時 (10s)'));
      }, 10000);

      clientSocket = io(`http://localhost:${port}/api-gateway`, {
        path: '/socket.io',
        timeout: 5000,
        reconnection: false,
      });

      welcomeListener = (data) => {
        console.log('[SPEC] 收到歡迎訊息:', data);
        welcomeMessageReceived = data;
        cleanupTimeoutsAndListeners();
        resolve();
      };
      clientSocket.on(WELCOME_EVENT, welcomeListener);

      clientSocket.on('connect', () => {
        console.log('[SPEC] 客戶端已連接到 /api-gateway (connect event)');
      });

      clientSocket.on('connect_error', (error) => {
        console.error('[SPEC] 客戶端連接錯誤:', error);
        cleanupTimeoutsAndListeners();
        reject(error);
      });
    });
    console.log('測試環境設置完成 (已收到歡迎訊息或超時)');
  });

  afterEach(async () => {
    console.log('清理測試環境...');
    if (clientSocket) {
      if (clientSocket.connected) {
        console.log('關閉客戶端 Socket...');
        clientSocket.disconnect(); // Use disconnect()
      }
      // Remove all listeners on clientSocket to be safe for next test
      clientSocket.removeAllListeners();
    }
    if (app) {
      console.log('關閉 NestJS 應用...');
      await app.close();
    }
    console.log('測試環境已清理');
  });

  it('應該能夠定義', () => {
    console.log('執行基本定義測試');
    expect(gateway).toBeDefined();
    console.log('基本定義測試完成');
  });

  describe('Connection', () => {
    it('應該能夠處理客戶端連接並接收歡迎訊息', () => {
      console.log('開始測試客戶端連接與歡迎訊息...');
      expect(welcomeMessageReceived).toBeTruthy(); // Check if message was received in beforeEach
      if (welcomeMessageReceived) {
        expect(welcomeMessageReceived).toHaveProperty('message');
        expect(welcomeMessageReceived).toHaveProperty('clientId');
        expect(welcomeMessageReceived).toHaveProperty('timestamp');
        console.log('[SPEC] 歡迎訊息驗證通過');
      }
      console.log('客戶端連接與歡迎訊息測試完成');
    });
  });

  describe('Room Management', () => {
    it('應該能夠處理加入房間', (done) => {
      console.log('開始測試加入房間...');
      const room = 'test-room';
      const timeout = setTimeout(() => {
        done(new Error('等待房間加入確認超時 (3s)'));
      }, 3000);

      clientSocket.on('room_joined', (data) => {
        console.log('收到房間加入確認:', data);
        expect(data).toHaveProperty('room', room);
        expect(data).toHaveProperty('timestamp');
        clearTimeout(timeout);
        console.log('加入房間測試完成');
        done();
      });

      clientSocket.emit('join_room', { room });
    }, 7000);

    it('應該能夠處理離開房間', (done) => {
      console.log('開始測試離開房間...');
      const room = 'test-room';
      const timeout = setTimeout(() => {
        done(new Error('等待房間離開確認超時 (3s)'));
      }, 3000);

      clientSocket.on('room_left', (data) => {
        console.log('收到房間離開確認:', data);
        expect(data).toHaveProperty('room', room);
        expect(data).toHaveProperty('timestamp');
        clearTimeout(timeout);
        console.log('離開房間測試完成');
        done();
      });

      clientSocket.emit('join_room', { room });
      clientSocket.emit('leave_room', { room });
    }, 7000);
  });

  describe('Message Broadcasting', () => {
    it('應該能夠廣播訊息給所有客戶端', (done) => {
      console.log('開始測試廣播訊息...');
      const event = 'test-event';
      const data = { message: 'test' };
      const timeout = setTimeout(() => {
        done(new Error('等待廣播訊息超時 (3s)'));
      }, 3000);

      clientSocket.on(event, (receivedData) => {
        console.log('收到廣播訊息:', receivedData);
        expect(receivedData).toEqual(expect.objectContaining(data));
        expect(receivedData).toHaveProperty('timestamp');
        clearTimeout(timeout);
        console.log('廣播訊息測試完成');
        done();
      });

      gateway.broadcastMessage(event, data);
    }, 7000);

    it('應該能夠發送訊息給特定客戶端', (done) => {
      console.log('開始測試發送訊息給特定客戶端...');
      const event = 'test-event';
      const data = { message: 'test' };
      const clientId = clientSocket.id || '';
      const timeout = setTimeout(() => {
        done(new Error('等待特定客戶端訊息超時 (3s)'));
      }, 3000);

      clientSocket.on(event, (receivedData) => {
        console.log('收到特定客戶端訊息:', receivedData);
        expect(receivedData).toEqual(expect.objectContaining(data));
        expect(receivedData).toHaveProperty('timestamp');
        clearTimeout(timeout);
        console.log('特定客戶端訊息測試完成');
        done();
      });

      gateway.sendToClient(clientId, event, data);
    }, 7000);

    it('應該能夠發送訊息給特定房間', (done) => {
      console.log('開始測試發送訊息給特定房間...');
      const room = 'test-room';
      const event = 'test-event';
      const data = { message: 'test' };
      const timeout = setTimeout(() => {
        done(new Error('等待房間訊息超時 (3s)'));
      }, 3000);

      // 清理之前的事件監聽器
      clientSocket.off('room_joined');
      clientSocket.off(event);

      // 加入房間
      clientSocket.emit('join_room', { room });
      
      // 等待確認加入房間
      clientSocket.on('room_joined', (joinData) => {
        console.log('成功加入房間:', joinData);
        
        // 設置事件監聽器
        clientSocket.on(event, (receivedData) => {
          console.log('收到房間訊息:', receivedData);
          expect(receivedData).toEqual(expect.objectContaining(data));
          expect(receivedData).toHaveProperty('timestamp');
          clearTimeout(timeout);
          console.log('房間訊息測試完成');
          done();
        });
        
        // 發送訊息
        gateway.sendToRoom(room, event, data);
      });
    }, 7000);
  });

  describe('Heartbeat', () => {
    it('應該能夠處理心跳機制', (done) => {
      console.log('開始測試心跳機制...');
      const timeout = setTimeout(() => {
        done(new Error('等待 pong 回應超時 (3s)'));
      }, 3000);

      clientSocket.on('pong', (data) => {
        console.log('收到 pong 回應:', data);
        expect(data).toHaveProperty('timestamp');
        clearTimeout(timeout);
        console.log('心跳測試完成');
        done();
      });

      clientSocket.emit('ping');
    }, 7000);
  });
}); 