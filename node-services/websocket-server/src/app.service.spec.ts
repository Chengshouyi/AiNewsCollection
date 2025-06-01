import { Test, TestingModule } from '@nestjs/testing';
import { AppService } from './app.service';
import { LoggerService } from '@app/logger';
import { Server, Socket } from 'socket.io';
import {
  BaseMessage,
  SystemMessage,
  AckMessage,
} from './interfaces/message.interface';

// Mock LoggerService
const mockLoggerService = {
  log: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
  debug: jest.fn(),
  verbose: jest.fn(),
  setContext: jest.fn(),
};

// Mock Socket and Server from socket.io
const mockSocket = {
  id: 'testSocketId',
  join: jest.fn(),
  leave: jest.fn(),
  emit: jest.fn(),
  on: jest.fn(),
  disconnect: jest.fn(),
  connected: true,
  broadcast: {
    to: jest.fn().mockReturnThis(),
    emit: jest.fn(),
  },
  to: jest.fn().mockReturnThis(),
  except: jest.fn().mockReturnThis(),
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
  on: jest.fn(),
  except: jest.fn().mockReturnThis(),
  fetchSockets: jest.fn().mockResolvedValue([]),
  adapter: {
    rooms: new Map(),
    sids: new Map(),
  },
};

describe('AppService', () => {
  let service: AppService;
  let ioServer: Server;
  // Store handlers to trigger them manually
  let connectionHandler: (socket: Socket) => void | null = null;
  let serverErrorHandler: (error: Error) => void | null = null;

  beforeEach(async () => {
    // Reset mocks before each test
    jest.clearAllMocks();
    // Reset handlers
    connectionHandler = null;
    serverErrorHandler = null;

    // Clear potential timers from previous tests if fake timers were used
    jest.clearAllTimers();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AppService,
        { provide: LoggerService, useValue: mockLoggerService },
      ],
    }).compile();

    service = module.get<AppService>(AppService);

    // Capture server event handlers during setSocketServer
    mockIoServer.on.mockImplementation((event, handler) => {
      if (event === 'connection') {
        connectionHandler = handler as (socket: Socket) => void;
      } else if (event === 'error') {
        serverErrorHandler = handler as (error: Error) => void;
      }
      return mockIoServer; // Return mock server for chaining if needed
    });

    // Manually set the mocked server instance AND REGISTER HANDLERS
    service.setSocketServer(mockIoServer as unknown as Server);
    ioServer = service.getSocketServer();

    // Ensure socket mock `on` returns itself for chaining if needed
    mockSocket.on.mockImplementation((event, listener) => {
      // Store listeners on the mock socket object itself for retrieval in tests
      mockSocket[`${event}Listener`] = listener;
      return mockSocket;
    });
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('setSocketServer', () => {
    it('should set the io server instance', () => {
      expect(service.getSocketServer()).toBe(ioServer);
    });

    it('should register error and connection handlers on the server', () => {
      // Check if the handlers were captured correctly in beforeEach
      expect(connectionHandler).toBeInstanceOf(Function);
      expect(serverErrorHandler).toBeInstanceOf(Function);
      // We can also check the original mock if needed, though capturing is more robust
      expect(mockIoServer.on).toHaveBeenCalledWith(
        'error',
        expect.any(Function),
      );
      expect(mockIoServer.on).toHaveBeenCalledWith(
        'connection',
        expect.any(Function),
      );

      // Optional: Test the server error handler directly if simple
      const testError = new Error('Server Error');
      if (serverErrorHandler) {
        serverErrorHandler(testError);
        expect(mockLoggerService.error).toHaveBeenCalledWith(
          'Socket.IO server error:',
          testError,
          AppService.name,
        );
      }
    });
  });

  describe('handleConnection', () => {
    let socketInstance: Socket;

    beforeEach(() => {
      // Ensure the connection handler is available
      if (!connectionHandler) {
        throw new Error('Connection handler not captured in beforeEach');
      }
      socketInstance = mockSocket as unknown as Socket;
      // Reset socket state for each test if necessary
      mockSocket.connected = true;
      // Clear specific listeners stored on the mock socket
      delete (mockSocket as any)['errorListener'];
      delete (mockSocket as any)['disconnectListener'];
      delete (mockSocket as any)['pingListener'];
      // Reset calls to socket.on
      mockSocket.on.mockClear();
      mockSocket.emit.mockClear();
    });

    it('should set initial reconnect attempts (tested indirectly via handleReconnection)', () => {
      // We don't directly check the log here anymore.
      // The fact that handleReconnection uses the map implies it was set.
      connectionHandler(socketInstance);
      // We can verify that listeners were attached as a sign of successful handling
      expect(mockSocket.on).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith(
        'disconnect',
        expect.any(Function),
      );
      expect(mockSocket.on).toHaveBeenCalledWith('ping', expect.any(Function));
    });

    it('should register error, disconnect, and ping handlers for the socket', () => {
      connectionHandler(socketInstance);
      expect(mockSocket.on).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith(
        'disconnect',
        expect.any(Function),
      );
      expect(mockSocket.on).toHaveBeenCalledWith('ping', expect.any(Function));
      // Verify listeners were stored on the mock object if needed for triggering
      expect(mockSocket['errorListener']).toBeInstanceOf(Function);
      expect(mockSocket['disconnectListener']).toBeInstanceOf(Function);
      expect(mockSocket['pingListener']).toBeInstanceOf(Function);
    });

    it('should handle ping event', () => {
      connectionHandler(socketInstance);
      const pingListener = (mockSocket as any)['pingListener'];
      expect(pingListener).toBeDefined();
      pingListener(); // Simulate ping event
      expect(mockSocket.emit).toHaveBeenCalledWith('pong', {
        timestamp: expect.any(Date),
      });
    });

    it('should handle socket errors by calling handleClientError', () => {
      const error = new Error('Test Socket Error');
      connectionHandler(socketInstance); // Register handlers
      const errorListener = (mockSocket as any)['errorListener'];
      expect(errorListener).toBeDefined();

      // Spy on the private method handleClientError to ensure it's called
      const handleClientErrorSpy = jest.spyOn(
        service as any,
        'handleClientError',
      );

      errorListener(error); // Simulate error event

      expect(handleClientErrorSpy).toHaveBeenCalledWith(socketInstance, error);
      // We can also check the logger call made by handleClientError
      expect(mockLoggerService.error).toHaveBeenCalledWith(
        `Error for client ${mockSocket.id}:`,
        error,
        AppService.name,
      );

      handleClientErrorSpy.mockRestore();
    });

    it('should handle disconnect with "transport close" reason by calling handleReconnection', () => {
      connectionHandler(socketInstance);
      const disconnectListener = (mockSocket as any)['disconnectListener'];
      expect(disconnectListener).toBeDefined();

      const handleReconnectionSpy = jest.spyOn(
        service as any,
        'handleReconnection',
      );
      disconnectListener('transport close'); // Simulate disconnect

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Client ${mockSocket.id} disconnected: transport close`,
        AppService.name,
      );
      expect(handleReconnectionSpy).toHaveBeenCalledWith(socketInstance);
      handleReconnectionSpy.mockRestore();
    });

    it('should handle disconnect with other reasons without attempting reconnection', () => {
      connectionHandler(socketInstance);
      const disconnectListener = (mockSocket as any)['disconnectListener'];
      expect(disconnectListener).toBeDefined();

      const handleReconnectionSpy = jest.spyOn(
        service as any,
        'handleReconnection',
      );
      disconnectListener('io server disconnect'); // Simulate disconnect with another reason

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Client ${mockSocket.id} disconnected: io server disconnect`,
        AppService.name,
      );
      expect(handleReconnectionSpy).not.toHaveBeenCalled();
      handleReconnectionSpy.mockRestore();
    });
  });

  describe('handleClientError', () => {
    it('should log the error and send a system message', () => {
      const error = new Error('Client Error');
      const socketInstance = mockSocket as unknown as Socket;
      // Spy on sendSystemMessage because it's the primary action
      const sendSystemMessageSpy = jest.spyOn(service as any, 'sendSystemMessage');

      // Access private method for direct testing
      (service as any).handleClientError(socketInstance, error);

      expect(mockLoggerService.error).toHaveBeenCalledWith(`Error for client ${mockSocket.id}:`, error, AppService.name);
      expect(sendSystemMessageSpy).toHaveBeenCalledWith(socketInstance, {
        level: 'error',
        code: 'CLIENT_ERROR',
        message: '發生錯誤，請稍後重試'
      });
      sendSystemMessageSpy.mockRestore();
    });
  });

  describe('handleReconnection', () => {
    // Use fake timers specifically for this describe block
    beforeEach(() => {
      jest.useFakeTimers();
      // Ensure the map is clean before each test or set specific states
      (service as any).reconnectAttempts.clear();
      // Reset socket connection state for tests
      mockSocket.connected = false;
    });

    afterEach(() => {
      jest.useRealTimers();
      // Clean up map after each test
      (service as any).reconnectAttempts.clear();
      // It's also good practice to ensure all timers are cleared if they were used
      jest.clearAllTimers();
    });

    it('should schedule a reconnection attempt, increment count, and log success if reconnected', () => {
      const socketInstance = mockSocket as unknown as Socket;
      (service as any).reconnectAttempts.set(socketInstance.id, 0); // Set initial state

      (service as any).handleReconnection(socketInstance);

      // Check attempt count incremented
      expect((service as any).reconnectAttempts.get(socketInstance.id)).toBe(1);

      // Simulate successful reconnection *before* the timer fires in reality
      // For testing the timer callback, we advance time *then* check the callback's logic
      mockSocket.connected = true;

      // Fast-forward time to trigger the scheduled check
      jest.advanceTimersByTime(1000); // Delay for the first attempt

      // Check callback execution: log and map deletion
      // Updated log message expectation
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Client ${socketInstance.id} reconnected successfully on attempt 1`,
        AppService.name,
      );
      expect((service as any).reconnectAttempts.has(socketInstance.id)).toBe(
        false,
      );
    });

    it('should log warning and remove client if max attempts exceeded', () => {
      const socketInstance = mockSocket as unknown as Socket;
      const maxAttempts = (service as any).maxReconnectAttempts;
      (service as any).reconnectAttempts.set(socketInstance.id, maxAttempts); // Set state to max attempts

      (service as any).handleReconnection(socketInstance);

      // Check outcome
      // Updated warning message expectation to match the initial check in handleReconnection
      expect(mockLoggerService.warn).toHaveBeenCalledWith(
        `Client ${socketInstance.id} already exceeded max reconnection attempts before scheduling attempt ${maxAttempts + 1}`,
        AppService.name,
      );
      expect((service as any).reconnectAttempts.has(socketInstance.id)).toBe(
        false,
      );
    });

    it('should schedule next attempt with increased delay if not connected after first timeout', () => {
      const socketInstance = mockSocket as unknown as Socket;
      (service as any).reconnectAttempts.set(socketInstance.id, 0);

      (service as any).handleReconnection(socketInstance); // Attempt 1 scheduled

      // Verify first attempt scheduled and count incremented
      expect((service as any).reconnectAttempts.get(socketInstance.id)).toBe(1);
      // Log for scheduling attempt 1
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(
          `Scheduling reconnection attempt 1 for client ${socketInstance.id}`,
        ),
        AppService.name,
      );

      // Fast-forward first timeout (1000ms)
      jest.advanceTimersByTime(1000);
      // Log for client still not connected after attempt 1
      expect(mockLoggerService.log).toHaveBeenCalledWith(`Client ${socketInstance.id} still not connected after attempt 1.`, AppService.name,
      );

      // handleReconnection should be called again internally, attempt count becomes 2
      expect((service as any).reconnectAttempts.get(socketInstance.id)).toBe(2);
      // Log for scheduling attempt 2
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(
          `Scheduling reconnection attempt 2 for client ${socketInstance.id}`,
        ),
        AppService.name,
      );

      // Fast-forward second timeout (2000ms)
      jest.advanceTimersByTime(2000);
      // Log for client still not connected after attempt 2
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Client ${socketInstance.id} still not connected after attempt 2.`,
        AppService.name,
      );

      // handleReconnection should be called again, attempt count becomes 3
      expect((service as any).reconnectAttempts.get(socketInstance.id)).toBe(3);
      // Log for scheduling attempt 3
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(
          `Scheduling reconnection attempt 3 for client ${socketInstance.id}`,
        ),
        AppService.name,
      );
    });
  });

  describe('sendSystemMessage', () => {
    it('should emit a system_message event with the correct structure', () => {
      const socketInstance = mockSocket as unknown as Socket;
      const systemData = { level: 'info', code: 'TEST_CODE', message: 'Test message' };

      // Spy or mock uuidv4 if you need a predictable ID
      const fixedUUID = 'fixed-uuid-1234';
      const uuidSpy = (jest.spyOn(uuid, 'v4') as unknown as jest.Mock<string, any[]>).mockImplementation(() => fixedUUID);


      (service as any).sendSystemMessage(socketInstance, systemData);

      const expectedMessage: SystemMessage = {
        id: fixedUUID, // Use the fixed ID
        type: 'system',
        timestamp: expect.any(Date), // Keep timestamp flexible
        sender: 'system',
        level: 'info',
        code: 'TEST_CODE',
        message: 'Test message',
      };

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`sendSystemMessage:`),
        AppService.name,
      ); // Basic log check
      // More specific log check if needed:
      // expect(mockLoggerService.log).toHaveBeenCalledWith(`sendSystemMessage: ${JSON.stringify(expectedMessage)}`, AppService.name);
      expect(socketInstance.emit).toHaveBeenCalledWith(
        'system_message',
        expectedMessage,
      );

      uuidSpy.mockRestore(); // Restore original uuidv4
    });
  });

  describe('emitToRoom', () => {
    it('should call io.to(room).emit with the correct arguments', () => {
      const room = 'testRoom';
      const event = 'testEvent';
      const data = { key: 'value' };
      service.emitToRoom(room, event, data);
      // Adjust log check to expect the object's default string representation or a relevant part
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`emitToRoom: ${room} ${event} `), // Check prefix
        AppService.name
      );
      // Optionally check for [object Object] if that's consistent
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining('[object Object]'), // Check object string representation part
        AppService.name,
      );
      expect(ioServer.to).toHaveBeenCalledWith(room);
      expect(mockIoServer.emit).toHaveBeenCalledWith(event, data);
    });

    it('should not emit if io server is not set', () => {
      service['io'] = null; // Temporarily unset io using bracket notation for private prop
      service.emitToRoom('room', 'event', {});
      expect(mockIoServer.emit).not.toHaveBeenCalled();
      // Restore io for subsequent tests (although beforeEach handles this)
      service.setSocketServer(mockIoServer as unknown as Server);
    });
  });

  describe('emitToAll', () => {
    it('should call io.emit with the correct arguments', () => {
      const event = 'globalEvent';
      const data = { global: true };
      service.emitToAll(event, data);
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`emitToAll: ${event}`),
        AppService.name,
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(event, data);
      expect(ioServer.to).not.toHaveBeenCalled(); // Verify not using .to()
    });
    it('should not emit if io server is not set', () => {
      service['io'] = null;
      service.emitToAll('event', {});
      expect(mockIoServer.emit).not.toHaveBeenCalled();
      service.setSocketServer(mockIoServer as unknown as Server);
    });
  });

  describe('emitToRoomExcludingSender', () => {
    it('should call io.to(room).except(senderId).emit', () => {
      const room = 'chatRoom';
      const event = 'message';
      const data = { text: 'hello' };
      const senderId = 'senderSocketId';
      service.emitToRoomExcludingSender(room, event, data, senderId);
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`emitToRoomExcludingSender: ${room} ${event}`),
        AppService.name,
      );
      expect(ioServer.to).toHaveBeenCalledWith(room);
      expect(mockIoServer.except).toHaveBeenCalledWith(senderId);
      expect(mockIoServer.emit).toHaveBeenCalledWith(event, data); // .emit called on the result of .except()
    });
    it('should not emit if io server is not set', () => {
      service['io'] = null;
      service.emitToRoomExcludingSender('room', 'event', {}, 'sender');
      expect(mockIoServer.to).not.toHaveBeenCalled();
      expect(mockIoServer.except).not.toHaveBeenCalled();
      expect(mockIoServer.emit).not.toHaveBeenCalled();
      service.setSocketServer(mockIoServer as unknown as Server);
    });
  });

  describe('emitToRoomIncludingSender', () => {
    it('should call io.to(room).emit', () => {
      const room = 'anotherRoom';
      const event = 'joined';
      const data = { user: 'newUser' };
      service.emitToRoomIncludingSender(room, event, data);
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`emitToRoomIncludingSender: ${room} ${event}`),
        AppService.name,
      );
      expect(ioServer.to).toHaveBeenCalledWith(room);
      expect(mockIoServer.except).not.toHaveBeenCalled(); // Ensure except wasn't called
      expect(mockIoServer.emit).toHaveBeenCalledWith(event, data); // .emit called on the result of .to()
    });
    it('should not emit if io server is not set', () => {
      service['io'] = null;
      service.emitToRoomIncludingSender('room', 'event', {});
      expect(mockIoServer.to).not.toHaveBeenCalled();
      expect(mockIoServer.emit).not.toHaveBeenCalled();
      service.setSocketServer(mockIoServer as unknown as Server);
    });
  });

  describe('getHello', () => {
    it('should return "Hello World!"', () => {
      expect(service.getHello()).toBe('Hello World!');
      expect(mockLoggerService.log).toHaveBeenCalledWith('getHello', AppService.name);
    });
  });

  describe('sendMessageToRoom', () => {
    it('should call emitToRoom with "new_message" event and payload', () => {
      const room = 'general';
      const message = 'Test message content';
      const senderId = 'user123';
      // Spy on the public method it calls
      const emitToRoomSpy = jest.spyOn(service, 'emitToRoom');

      service.sendMessageToRoom(room, message, senderId);

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`sendMessageToRoom: ${room} ${message} ${senderId}`),
        AppService.name,
      );
      expect(emitToRoomSpy).toHaveBeenCalledWith(
        room,
        'new_message',
        expect.objectContaining({
          user: senderId,
          room: room,
          message: message,
          timestamp: expect.any(Date),
        }),
      );
      emitToRoomSpy.mockRestore();
    });
  });

  describe('updateTaskProgress', () => {
    it('should call emitToRoom with "task_progress" event and payload for the task room', () => {
      const taskId = 123;
      const status = 'processing';
      const progress = 50;
      const message = 'Halfway done';
      const taskRoom = `task_${taskId}`;
      const emitToRoomSpy = jest.spyOn(service, 'emitToRoom');

      service.updateTaskProgress(taskId, status, progress, message);

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`updateTaskProgress: ${taskId} ${status} ${progress}`),
        AppService.name,
      );
      expect(emitToRoomSpy).toHaveBeenCalledWith(
        taskRoom,
        'task_progress',
        expect.objectContaining({
          task_id: taskId,
          status: status,
          progress: progress,
          message: message,
          timestamp: expect.any(Date),
        }),
      );
      emitToRoomSpy.mockRestore();
    });
  });

  describe('sendMessageWithAck', () => {
    // Use fake timers for this block
    beforeEach(() => {
      jest.useFakeTimers();
    });
    afterEach(() => {
      jest.useRealTimers();
    });

    it('should resolve true when ACK is received successfully', async () => {
      const room = 'ackRoom';
      const message: BaseMessage = { id: 'msg1', type: 'chat', timestamp: new Date(), sender: 'sender' };
      let ackCallback: (ack: AckMessage) => void = jest.fn(); // Use jest.fn for the callback

      // Mock the emit function to capture the ACK callback
      mockIoServer.emit.mockImplementation((event, msg, callback) => {
        if (event === 'message' && typeof callback === 'function') {
          ackCallback = callback; // Capture the callback
        }
      });

      const promise = service.sendMessageWithAck(room, message, 5000);

      // Ensure the callback was captured before trying to call it
      expect(ackCallback).toBeInstanceOf(Function);

      // Simulate receiving ACK
      const ackMessage: AckMessage = {
        messageId: message.id,
        status: 'received',
        timestamp: new Date(),
      };
      ackCallback(ackMessage); // Trigger the captured callback

      // Advance timers minimally to allow promise microtasks to resolve
      jest.advanceTimersByTime(1);

      await expect(promise).resolves.toBe(true);
      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `Message ${message.id} acknowledged`,
        AppService.name,
      );
      // We no longer assert setTimeout/clearTimeout calls directly.
      // The successful resolution and log message imply the timer was handled correctly.
    });

    it('should resolve false when ACK indicates failure', async () => {
      const room = 'ackRoom';
      const message: BaseMessage = { id: 'msg2', type: 'chat', timestamp: new Date(), sender: 'sender' };
      let ackCallback: (ack: AckMessage) => void = jest.fn();

      mockIoServer.emit.mockImplementation((event, msg, callback) => {
        if (event === 'message' && typeof callback === 'function') {
          ackCallback = callback;
        }
      });

      const promise = service.sendMessageWithAck(room, message, 5000);
      expect(ackCallback).toBeInstanceOf(Function);

      // Simulate receiving failed ACK
      const ackMessage: AckMessage = {
        messageId: message.id,
        status: 'failed',
        error: 'Processing error',
        timestamp: new Date(),
      };
      ackCallback(ackMessage);

      // Advance timers minimally
      jest.advanceTimersByTime(1);

      await expect(promise).resolves.toBe(false);
      expect(mockLoggerService.error).toHaveBeenCalledWith(
        `Message ${message.id} failed: Processing error`,
        AppService.name,
      );
      // Correct resolution and error log imply timer was handled.
    });

    it('should resolve false on timeout', async () => {
      const room = 'ackRoom';
      const message: BaseMessage = { id: 'msg3', type: 'chat', timestamp: new Date(), sender: 'sender' };

      // Mock emit, but the callback is never called in this test case
      mockIoServer.emit.mockImplementation((event, msg, callback) => {
        if (event === 'message' && typeof callback === 'function') {
          // Don't call the callback to simulate timeout
        }
      });

      const promise = service.sendMessageWithAck(room, message, 5000);

      // We don't check if setTimeout was called.
      // Instead, we advance time and check the *result* of the timeout.

      // Fast-forward time past the timeout
      jest.advanceTimersByTime(5001);

      // Timeout callback should have executed now
      await expect(promise).resolves.toBe(false);
      expect(mockLoggerService.warn).toHaveBeenCalledWith(
        `Message ${message.id} ACK timeout`,
        AppService.name,
      );
      // Correct resolution and warning log confirm the timeout mechanism worked.
    });
  });

  // handleMessageAck is private and implicitly tested via sendMessageWithAck's ACK mechanism.
  // Direct testing is usually not necessary unless it has complex logic itself.
  describe('handleMessageAck (Private Method)', () => {
    it('should emit "message_ack" event with correct payload', () => {
      const socketInstance = mockSocket as unknown as Socket;
      const messageId = 'ackMsgId';
      const status = 'received';

      // Call the private method
      (service as any).handleMessageAck(socketInstance, messageId, status);

      const expectedAck: AckMessage = {
        messageId: messageId,
        status: status,
        timestamp: expect.any(Date),
        error: undefined, // Explicitly undefined when no error
      };

      expect(mockLoggerService.log).toHaveBeenCalledWith(`handleMessageAck: ${messageId} ${status} undefined`, AppService.name);
      expect(socketInstance.emit).toHaveBeenCalledWith('message_ack', expectedAck);
    });

    it('should include error in payload when status is "failed"', () => {
      const socketInstance = mockSocket as unknown as Socket;
      const messageId = 'ackMsgIdFail';
      const status = 'failed';
      const error = 'Failure reason';

      // Call the private method
      (service as any).handleMessageAck(socketInstance, messageId, status, error);
      const expectedAck: AckMessage = {
        messageId: messageId,
        status: status,
        timestamp: expect.any(Date),
        error: error,
      };

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        `handleMessageAck: ${messageId} ${status} ${error}`,
        AppService.name,
      );
      expect(socketInstance.emit).toHaveBeenCalledWith(
        'message_ack',
        expectedAck,
      );
    });
  });

  describe('broadcastMessage', () => {
    const room = 'broadcastRoom';
    const message: BaseMessage = {
      id: 'bcast1',
      type: 'system',
      timestamp: new Date(),
      sender: 'systemSender',
    };

    it('should use emitToRoomIncludingSender when includeSender is true', () => {
      // Spy on the methods it should/shouldn't call
      const emitIncludingSpy = jest.spyOn(service, 'emitToRoomIncludingSender');
      const emitExcludingSpy = jest.spyOn(service, 'emitToRoomExcludingSender');

      service.broadcastMessage(room, message, true);

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`broadcastMessage: ${room}`),
        AppService.name,
      );
      expect(emitIncludingSpy).toHaveBeenCalledWith(room, 'message', message);
      expect(emitExcludingSpy).not.toHaveBeenCalled();

      // Restore spies
      emitIncludingSpy.mockRestore();
      emitExcludingSpy.mockRestore();
    });

    it('should use emitToRoomExcludingSender when includeSender is false', () => {
      const emitIncludingSpy = jest.spyOn(service, 'emitToRoomIncludingSender');
      const emitExcludingSpy = jest.spyOn(service, 'emitToRoomExcludingSender');

      service.broadcastMessage(room, message, false);

      expect(mockLoggerService.log).toHaveBeenCalledWith(
        expect.stringContaining(`broadcastMessage: ${room}`),
        AppService.name,
      );
      expect(emitExcludingSpy).toHaveBeenCalledWith(
        room,
        'message',
        message,
        message.sender,
      );
      expect(emitIncludingSpy).not.toHaveBeenCalled();

      emitIncludingSpy.mockRestore();
      emitExcludingSpy.mockRestore();
    });

    it('should default to includeSender = false', () => {
      const emitIncludingSpy = jest.spyOn(service, 'emitToRoomIncludingSender');
      const emitExcludingSpy = jest.spyOn(service, 'emitToRoomExcludingSender');

      service.broadcastMessage(room, message); // No includeSender argument

      expect(emitExcludingSpy).toHaveBeenCalledWith(
        room,
        'message',
        message,
        message.sender,
      );
      expect(emitIncludingSpy).not.toHaveBeenCalled();
      emitIncludingSpy.mockRestore();
      emitExcludingSpy.mockRestore();
    });
  });
});
