import { Test, TestingModule } from '@nestjs/testing';
import { TasksGateway } from './tasks.gateway';
import { RedisService } from '../shared/redis/redis.service';
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';
import { Server, Socket } from 'socket.io';

// 模擬 (Mock) 相依性
const mockRedisService = {
  subscribe: jest.fn(),
  // 如果 RedisService 有其他被 TasksGateway 使用的方法，也需在此模擬
};

const mockConfigService = {
  get: jest.fn().mockReturnValue('redis://mock-redis:6379'), // 提供一個模擬的 REDIS_URL
};

const mockLoggerService = {
  log: jest.fn(),
  debug: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
  verbose: jest.fn(),
};

// 模擬 Socket.IO Server
const mockIoServer = {
  to: jest.fn().mockReturnThis(), // 鏈式呼叫 .to().emit()
  emit: jest.fn(),
};

// 模擬 Socket.IO Client
const mockIoSocket = {
  id: 'mockSocketId',
  join: jest.fn(),
  emit: jest.fn(),
  // 如果有使用 client 的其他方法或屬性，也需在此模擬
};


describe('TasksGateway', () => {
  let gateway: TasksGateway;
  let redisService: RedisService;
  let configService: ConfigService;
  let loggerService: LoggerService;
  let server: Server;
  // let socket: Socket; // Socket 通常在每個測試案例中建立或模擬

  beforeEach(async () => {
    // 將清除 mocks 的操作移到最前面
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TasksGateway,
        { provide: RedisService, useValue: mockRedisService },
        { provide: ConfigService, useValue: mockConfigService },
        { provide: LoggerService, useValue: mockLoggerService },
      ],
    }).compile();

    // 在這裡實例化 Gateway 時，會呼叫 constructor 並記錄 log
    gateway = module.get<TasksGateway>(TasksGateway);
    redisService = module.get<RedisService>(RedisService);
    configService = module.get<ConfigService>(ConfigService);
    loggerService = module.get<LoggerService>(LoggerService);

    gateway.server = mockIoServer as unknown as Server;

    // 不再需要在末尾清除 mocks
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  // --- 測試案例將會加在這裡 ---

  describe('handleConnection', () => {
    it('應該記錄客戶端連線', () => {
      const mockClient = { id: 'client-123' } as Socket;
      gateway.handleConnection(mockClient);
      expect(loggerService.log).toHaveBeenCalledWith(`客戶端已連線: ${mockClient.id}`);
    });
  });

  describe('handleDisconnect', () => {
    it('應該記錄客戶端斷線', () => {
      const mockClient = { id: 'client-456' } as Socket;
      gateway.handleDisconnect(mockClient);
      expect(loggerService.log).toHaveBeenCalledWith(`客戶端已斷線: ${mockClient.id}`);
    });
  });

  describe('handleJoinRoom', () => {
    it('應該讓客戶端加入指定房間並發送 joined_room 事件', () => {
      const roomName = 'test-room';
      const mockClient = { ...mockIoSocket } as unknown as Socket; // 使用複製的 mockSocket
      const data = { room: roomName };

      gateway.handleJoinRoom(data, mockClient);

      expect(mockClient.join).toHaveBeenCalledWith(roomName);
      expect(mockClient.emit).toHaveBeenCalledWith('joined_room', { room: roomName });
      expect(loggerService.log).toHaveBeenCalledWith(`客戶端 ${mockClient.id} 加入房間: ${roomName}`);
    });
  });

  describe('broadcastToRoom', () => {
    it('應該廣播事件和資料到指定房間', () => {
      const roomName = 'broadcast-room';
      const eventName = 'test-event';
      const payload = { message: 'hello room' };

      gateway.broadcastToRoom(roomName, eventName, payload);

      expect(mockIoServer.to).toHaveBeenCalledWith(roomName);
      expect(mockIoServer.emit).toHaveBeenCalledWith(eventName, payload);
    });
  });

  describe('onModuleInit', () => {
    it('應該訂閱 Redis 的 task_events 頻道', () => {
      gateway.onModuleInit();
      expect(redisService.subscribe).toHaveBeenCalledWith('task_events', expect.any(Function));
    });

    it('收到 Redis 訊息時應該廣播到對應房間', () => {
      // 1. 呼叫 onModuleInit 來設定訂閱
      gateway.onModuleInit();

      // 2. 取得傳遞給 redisService.subscribe 的回呼函式
      //    第一次呼叫 subscribe 的第二個參數就是那個回呼函式
      const redisCallback = mockRedisService.subscribe.mock.calls[0][1];

      // 3. 模擬從 Redis 收到訊息
      const message = {
        room: 'redis-room',
        event: 'redis-event',
        data: { detail: 'from redis' },
      };
      redisCallback(message);

      // 4. 驗證是否正確廣播到 Socket.IO 房間
      expect(mockIoServer.to).toHaveBeenCalledWith(message.room);
      expect(mockIoServer.emit).toHaveBeenCalledWith(message.event, message.data);
      expect(loggerService.debug).toHaveBeenCalledWith(`已從 Redis 收到事件並廣播到房間: ${message.room}, 事件: ${message.event}`);
    });
  });

   describe('Constructor', () => {
    it('應該從 ConfigService 取得 REDIS_URL 並記錄', () => {
        // 現在這個斷言應該可以通過了，因為 log 呼叫發生在 beforeEach 中，
        // 且 clearAllMocks 在呼叫之前執行 (清除了上個測試的記錄)
        expect(mockLoggerService.log).toHaveBeenCalledWith('Redis URL: redis://mock-redis:6379');
    });
  });

});
