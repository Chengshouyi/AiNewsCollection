import { Test, TestingModule } from '@nestjs/testing';
import { MessageQueueService } from './message-queue.service';
import { LoggerService } from '@app/logger';
import { BaseMessage, ChatMessage, TaskMessage } from '../interfaces/message.interface';

describe('MessageQueueService', () => {
  let service: MessageQueueService;
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

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MessageQueueService,
        {
          provide: LoggerService,
          useValue: mockLoggerService,
        },
      ],
    }).compile();

    service = module.get<MessageQueueService>(MessageQueueService);
    loggerService = module.get<LoggerService>(LoggerService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('訊息佇列管理', () => {
    const mockMessage: ChatMessage = {
      id: 'test-message-id',
      type: 'chat',
      content: '測試訊息',
      timestamp: new Date(),
      sender: 'test-user',
      room: 'test-room'
    };

    it('應該正確將訊息加入佇列', async () => {
      await service.queueMessage('test-room', mockMessage);
      const messages = await service.getQueuedMessages('test-room');
      expect(messages).toHaveLength(1);
      expect(messages[0]).toEqual(mockMessage);
    });

    it('當獲取佇列訊息後應該清空佇列', async () => {
      await service.queueMessage('test-room', mockMessage);
      await service.getQueuedMessages('test-room');
      const messages = await service.getQueuedMessages('test-room');
      expect(messages).toHaveLength(0);
    });

    it('當獲取不存在的房間訊息時應該返回空陣列', async () => {
      const messages = await service.getQueuedMessages('non-existent-room');
      expect(messages).toHaveLength(0);
    });
  });

  describe('訊息歷史記錄管理', () => {
    const mockMessages: ChatMessage[] = Array.from({ length: 110 }, (_, i) => ({
      id: `test-message-${i}`,
      type: 'chat',
      content: `測試訊息 ${i}`,
      timestamp: new Date(),
      sender: 'test-user',
      room: 'test-room'
    }));

    it('應該正確儲存訊息到歷史記錄', async () => {
      await service.saveToHistory('test-room', mockMessages[0]);
      const history = await service.getMessageHistory('test-room');
      expect(history).toHaveLength(1);
      expect(history[0]).toEqual(mockMessages[0]);
    });

    it('應該限制歷史記錄大小', async () => {
      for (const message of mockMessages) {
        await service.saveToHistory('test-room', message);
      }
      const history = await service.getMessageHistory('test-room');
      expect(history.length).toBeLessThanOrEqual(100);
    });

    it('應該正確獲取指定數量的歷史訊息', async () => {
      for (const message of mockMessages.slice(0, 10)) {
        await service.saveToHistory('test-room', message);
      }
      const history = await service.getMessageHistory('test-room', 5);
      expect(history).toHaveLength(5);
    });

    it('當獲取不存在的房間歷史記錄時應該返回空陣列', async () => {
      const history = await service.getMessageHistory('non-existent-room');
      expect(history).toHaveLength(0);
    });

    it('應該正確清除歷史記錄', async () => {
      await service.saveToHistory('test-room', mockMessages[0]);
      await service.clearHistory('test-room');
      const history = await service.getMessageHistory('test-room');
      expect(history).toHaveLength(0);
    });
  });
}); 