import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';
import { LoggerService } from '@app/logger';
import { RedisService } from './redis.service';

// 模擬 ioredis
jest.mock('ioredis', () => {
  // 函數：創建一個新的、獨立的模擬 Redis 實例
  const createMockRedisInstance = () => {
    const mockInstance = {
      _messageHandler: null as unknown as (
        event: string,
        handler: (...args: any[]) => void,
      ) => void | null,
      // 模擬 on 方法
      on: jest.fn((event: string, handler: (...args: any[]) => void) => {
        if (event === 'message') {
          // 儲存傳遞給 'message' 事件的處理函數
          mockInstance._messageHandler = handler as unknown as (
            event: string,
            handler: (...args: any[]) => void,
          ) => void | null;
        }
        // 返回 this (mockInstance) 以允許鏈式調用
        return mockInstance as unknown as Redis;
      }),
      quit: jest.fn().mockResolvedValue('OK'),
      publish: jest.fn().mockResolvedValue(1),
      subscribe: jest.fn((channel, callback) => {
        // 模擬成功訂閱的回調
        if (callback) {
          (callback as (err: Error | null, count: number) => void)(null, 1); // null 表示沒有錯誤，1 表示頻道數量
        }
        // subscribe 本身不需要模擬添加 message handler，on 的模擬會處理
        return Promise.resolve();
      }),
      // 模擬觸發消息的方法（每個實例獨立）
      _triggerMessage: (channel: string, message: string) => {
        const messageHandler = (
          mockInstance as unknown as {
            _messageHandler: (channel: string, message: string) => void;
          }
        )._messageHandler;
        if (messageHandler) {
          // 調用儲存的處理函數，模擬 ioredis 的行為
          (messageHandler as (channel: string, message: string) => void)(
            channel,
            message,
          );
        }
      },
      // 可以根據需要添加其他模擬方法
    };
    return mockInstance as unknown as Redis;
  };

  // 返回模擬模組的結構
  return {
    __esModule: true, // 表明是 ES 模組模擬
    // 模擬預設導出的建構函式，每次調用都創建新實例
    default: jest.fn().mockImplementation(createMockRedisInstance),
  };
});

// 模擬 LoggerService
const mockLoggerService = {
  log: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
};

// 模擬 ConfigService
const mockConfigService = {
  get: jest.fn((key: string, defaultValue?: any) => {
    if (key === 'REDIS_URL') {
      return 'redis://mock-redis:6379';
    }
    return defaultValue as string;
  }),
};

describe('RedisService', () => {
  let service: RedisService;
  let redisClient: Redis; // 類型保持不變
  let redisSubscriber: Redis; // 類型保持不變

  beforeEach(async () => {
    // 重置所有 Mocks
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RedisService,
        { provide: ConfigService, useValue: mockConfigService },
        { provide: LoggerService, useValue: mockLoggerService },
      ],
    }).compile();

    service = module.get<RedisService>(RedisService);

    // 模擬 onModuleInit 以觸發 Redis 實例創建
    service.onModuleInit();

    // 從模擬的 Redis 構造函數獲取獨立的實例
    // 首先轉換為 'unknown'，然後再轉換為 jest.Mock，以解決類型重疊問題
    const instancesResults = (Redis as unknown as jest.Mock).mock.results;

    if (!instancesResults || instancesResults.length < 2) {
      throw new Error('模擬 Redis 建構函數未按預期被調用兩次');
    }

    // .mock.results 包含模擬函數每次調用的返回值 (即我們的 mockInstance)
    // 確保 value 存在，因為 result 的類型可能是 { type: 'return' | 'throw', value: any }
    if (
      instancesResults[0]?.type !== 'return' ||
      instancesResults[1]?.type !== 'return'
    ) {
      throw new Error('模擬 Redis 建構函數調用未成功返回');
    }
    redisClient = instancesResults[0].value as Redis;
    redisSubscriber = instancesResults[1].value as Redis;

    // 你可以在這裡加一個檢查，確認它們是不同的物件：
    // console.log('Client 和 Subscriber 是否為同一個模擬物件？', redisClient === redisSubscriber); // 應該輸出 false
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('onModuleInit', () => {
    it('應該初始化 Redis 客戶端和訂閱者', async () => {
      expect(mockConfigService.get).toHaveBeenCalledWith(
        'REDIS_URL',
        'redis://localhost:6379',
      );
      // 檢查 Redis 模擬建構函數被調用了兩次
      expect(Redis).toHaveBeenCalledTimes(2);
      expect(Redis).toHaveBeenCalledWith('redis://mock-redis:6379');
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'Connecting to Redis at redis://mock-redis:6379',
        RedisService.name,
      );
    });

    it('應該附加客戶端和訂閱者的 connect 和 error 監聽器', () => {
      // 檢查 client 的監聽器
      expect((redisClient.on as jest.Mock).mock.calls[0][0]).toBe('connect');
      expect((redisClient.on as jest.Mock).mock.calls[1][0]).toBe('error');
      // 檢查 subscriber 的監聽器
      expect((redisSubscriber.on as jest.Mock).mock.calls[0][0]).toBe(
        'connect',
      );
      expect((redisSubscriber.on as jest.Mock).mock.calls[1][0]).toBe('error');
      // 注意：'message' 監聽器的檢查已移至 subscribe 的測試中
    });

    it('應該記錄 connect 和 error 事件的訊息', () => {
      // 從 client 的呼叫中找到回調
      const clientConnectCallback = (
        redisClient.on as jest.Mock
      ).mock.calls.find((call) => call[0] === 'connect')?.[1] as
        | (() => void)
        | undefined;
      const clientErrorCallback = (redisClient.on as jest.Mock).mock.calls.find(
        (call) => call[0] === 'error',
      )?.[1] as (error: Error) => void | undefined;

      // 從 subscriber 的呼叫中找到回調
      const subscriberConnectCallback = (
        redisSubscriber.on as jest.Mock
      ).mock.calls.find((call) => call[0] === 'connect')?.[1] as
        | (() => void)
        | undefined;
      const subscriberErrorCallback = (
        redisSubscriber.on as jest.Mock
      ).mock.calls.find((call) => call[0] === 'error')?.[1] as
        | ((error: Error) => void)
        | undefined;

      // 觸發並驗證 client 的日誌
      if (clientConnectCallback) clientConnectCallback();
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'Redis client connected',
        RedisService.name,
      );
      const clientError = new Error('Client connection error');
      if (clientErrorCallback) clientErrorCallback(clientError);
      expect(mockLoggerService.error).toHaveBeenCalledWith(
        'Redis client error',
        clientError,
        RedisService.name,
      );

      // 觸發並驗證 subscriber 的日誌
      if (subscriberConnectCallback) subscriberConnectCallback();
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'Redis subscriber connected',
        RedisService.name,
      );
      const subscriberError = new Error('Subscriber connection error');
      if (subscriberErrorCallback) subscriberErrorCallback(subscriberError);
      expect(mockLoggerService.error).toHaveBeenCalledWith(
        'Redis subscriber error',
        subscriberError,
        RedisService.name,
      );
    });
  });

  describe('onModuleDestroy', () => {
    it('應該關閉客戶端和訂閱者的連接', async () => {
      await service.onModuleDestroy();
      // 現在應該各自只被呼叫一次
      expect(redisClient.quit).toHaveBeenCalledTimes(1);
      expect(redisSubscriber.quit).toHaveBeenCalledTimes(1);
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'Redis connections closed',
        RedisService.name,
      );
    });

    it('應該處理客戶端或訂閱者未初始化的情况', async () => {
      service['client'] = null;
      service['subscriber'] = null;
      expect(service.onModuleDestroy()).not.toThrow();
      // quit 不會被呼叫，但關閉日誌應該仍然記錄
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'Redis connections closed',
        RedisService.name,
      );
    });
  });

  describe('getClient', () => {
    it('應該返回 Redis 客戶端實例', () => {
      const client = service.getClient();
      expect(client).toBe(redisClient); // 應該是 client 實例
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        'getClient',
        RedisService.name,
      );
    });
  });

  describe('publish', () => {
    it('應該發送訊息到指定的頻道', async () => {
      const channel = 'test-channel';
      const message = { data: 'test-data' };
      await service.publish(channel, message);
      // **修正：** 期望日誌中的 message 為 '[object Object]'
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `publish: ${channel} ${message}`,
        RedisService.name,
      );
      // 驗證 client 的 publish 方法被正確呼叫（這部分不變）
      expect(redisClient.publish).toHaveBeenCalledWith(
        channel,
        JSON.stringify(message),
      );
    });
  });

  describe('subscribe', () => {
    const channel = 'test-subscribe-channel';
    const handler = jest.fn();

    beforeEach(() => {
      handler.mockClear();
    });

    it('應該訂閱指定的頻道', () => {
      service.subscribe(channel, handler);
      expect(redisSubscriber.subscribe).toHaveBeenCalledWith(
        channel,
        expect.any(Function),
      );
    });

    // **新增/移動：** 驗證 'message' 監聽器是否已附加
    it('應該為訂閱者附加 message 監聽器', () => {
      service.subscribe(channel, handler);
      expect(redisSubscriber.on).toHaveBeenCalledWith(
        'message',
        expect.any(Function),
      );
    });

    it('應該記錄訂閱成功的訊息', () => {
      service.subscribe(channel, handler);
      // 模擬的回調已在 jest.mock 中被調用
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Redis 已訂閱 ${channel} 頻道`,
        RedisService.name,
      );
    });

    it('應該記錄訂閱失敗的訊息', () => {
      const error = new Error('Subscription failed');
      (redisSubscriber.subscribe as jest.Mock).mockImplementationOnce(
        (ch, cb) => {
          if (cb) {
            cb(error, 0); // 模擬錯誤
          }
          return Promise.resolve(); // 仍然返回 Promise
        },
      );

      service.subscribe(channel, handler);
      expect(mockLoggerService.error).toHaveBeenCalledWith(
        `Redis 訂閱失敗: ${error}`,
        RedisService.name,
      );
      // 恢復正常的模擬
    });

    it('應該在收到訊息時用解析的 JSON 訊息呼叫處理函數', () => {
      service.subscribe(channel, handler);
      const messagePayload = { key: 'value' };
      const messageString = JSON.stringify(messagePayload);

      // 觸發 message 事件 (使用 subscriber 實例的 _triggerMessage)
      redisSubscriber._triggerMessage(channel, messageString);

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith(messagePayload);
    });

    it('應該用原始訊息呼叫處理函數，並記錄 JSON 解析失敗的警告', () => {
      service.subscribe(channel, handler);
      const invalidMessageString = 'this is not json';

      // 觸發 message 事件
      redisSubscriber._triggerMessage(channel, invalidMessageString);

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith(invalidMessageString);
      expect(mockLoggerService.warn).toHaveBeenCalledWith(
        expect.stringContaining('Redis 訊息解析失敗:'), // 檢查警告訊息的開頭是否正確
        RedisService.name,
      );
    });

    it('應該在收到不同頻道的訊息時不呼叫處理函數', () => {
      service.subscribe(channel, handler);
      const messagePayload = { key: 'value' };
      const messageString = JSON.stringify(messagePayload);

      // 觸發 message 事件，但使用不同的 channel
      redisSubscriber._triggerMessage('another-channel', messageString);

      // 處理函數不應該被呼叫，因為 service 內的 on('message') 處理函數會檢查頻道
      expect(handler).not.toHaveBeenCalled();
    });
  });
});
