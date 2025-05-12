import { bootstrap } from './main';

// Mock @nestjs/core
const mockAppGet = jest.fn();
const mockUseLogger = jest.fn();
const mockHttpAdapterInstance = { getInstance: jest.fn().mockReturnValue({}) };
const mockGetHttpAdapter = jest.fn().mockReturnValue(mockHttpAdapterInstance);
const mockNestApp = {
  get: mockAppGet,
  useLogger: mockUseLogger,
  getHttpAdapter: mockGetHttpAdapter,
};
const mockNestFactoryCreate = jest.fn().mockResolvedValue(mockNestApp);
jest.mock('@nestjs/core', () => ({
  NestFactory: {
    create: (...args: any[]) => mockNestFactoryCreate(...args),
  },
}));

// Mock ./app.module (placeholder)
jest.mock('./app.module', () => ({
  AppModule: class AppModule {},
}));

// Mock http
const mockHttpServerListen = jest.fn().mockResolvedValue(undefined);
const mockHttpServer = {
  listen: mockHttpServerListen,
};
const mockCreateServer = jest.fn().mockReturnValue(mockHttpServer);
jest.mock('http', () => ({
  createServer: (...args: any[]) => mockCreateServer(...args),
}));

// Mock socket.io
const mockIoOn = jest.fn();
const mockSocketOn = jest.fn();
const mockSocketJoin = jest.fn();
const mockSocketLeave = jest.fn();
const mockSocketEmit = jest.fn();
const mockClientSocket = {
  id: 'test-socket-id',
  on: mockSocketOn,
  join: mockSocketJoin,
  leave: mockSocketLeave,
  emit: mockSocketEmit,
};
const mockIoServerInstance = {
  on: mockIoOn,
};
const mockSocketIoServerConstructor = jest.fn().mockReturnValue(mockIoServerInstance);
jest.mock('socket.io', () => ({
  Server: jest.fn().mockImplementation((...args) => mockSocketIoServerConstructor(...args)),
}));

// Mock ./app.service
const mockSetSocketServer = jest.fn();
const mockAppServiceInstance = {
  setSocketServer: mockSetSocketServer,
};
jest.mock('./app.service', () => ({
  // Ensure AppService is a constructor function for `new AppService()` if used,
  // or a factory if `app.get(AppService)` expects a class.
  // For app.get(AppService), NestJS expects a class/token.
  // The mock here is for when `main.ts` imports `AppService`
  AppService: jest.fn(() => mockAppServiceInstance),
}));

// Mock @nestjs/config
const mockConfigServiceGet = jest.fn();
const mockConfigServiceInstance = {
  get: mockConfigServiceGet,
};
jest.mock('@nestjs/config', () => ({
  ConfigService: jest.fn(() => mockConfigServiceInstance),
}));

// Mock @app/logger
const mockLoggerLog = jest.fn();
const mockLoggerError = jest.fn();
const mockLoggerServiceInstance = {
  log: mockLoggerLog,
  error: mockLoggerError,
};
jest.mock('@app/logger', () => ({
  LoggerService: jest.fn(() => mockLoggerServiceInstance),
}));

// Import actual classes for type checking in mockAppGet after mocks are defined.
// jest.mock hoists, so these will reference the mocked versions if not careful,
// but for `app.get(Token)`, Token is the class constructor.
import { AppModule } from './app.module';
import { AppService } from './app.service';
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';


describe('bootstrap', () => {
  let capturedConnectionHandler: (socket: any) => void;
  let capturedSocketEventHandlers: Record<string, (data?: any) => void>;

  beforeEach(() => {
    jest.clearAllMocks();
    capturedSocketEventHandlers = {};

    // Configure mockAppGet to return correct instances based on the token
    mockAppGet.mockImplementation((token: any) => {
      if (token === LoggerService) return mockLoggerServiceInstance;
      if (token === ConfigService) return mockConfigServiceInstance;
      if (token === AppService) return mockAppServiceInstance;
      return undefined;
    });
    
    // Default config service behavior
    mockConfigServiceGet.mockImplementation((key: string, defaultValue?: any) => {
      if (key === 'CORS_ORIGIN') return defaultValue !== undefined ? defaultValue : '*';
      if (key === 'PORT') return undefined; // To test default 4000
      return undefined;
    });

    // Capture Socket.IO server 'connection' event handler
    mockIoOn.mockImplementation((event: string, handler: (socket: any) => void) => {
      if (event === 'connection') {
        capturedConnectionHandler = handler;
      }
    });

    // Capture individual client socket event handlers
    mockSocketOn.mockImplementation((event: string, handler: (data?: any) => void) => {
      capturedSocketEventHandlers[event] = handler;
    });
  });

  it('should initialize NestJS app, HTTP and Socket.IO servers with default port and CORS', async () => {
    await bootstrap();

    expect(mockNestFactoryCreate).toHaveBeenCalledWith(AppModule, { logger: false });
    expect(mockAppGet).toHaveBeenCalledWith(LoggerService);
    expect(mockUseLogger).toHaveBeenCalledWith(mockLoggerServiceInstance);
    expect(mockAppGet).toHaveBeenCalledWith(ConfigService);
    expect(mockAppGet).toHaveBeenCalledWith(AppService);

    expect(mockGetHttpAdapter).toHaveBeenCalled();
    expect(mockHttpAdapterInstance.getInstance).toHaveBeenCalled();
    expect(mockCreateServer).toHaveBeenCalledWith(mockHttpAdapterInstance.getInstance());

    expect(mockSocketIoServerConstructor).toHaveBeenCalledWith(mockHttpServer, {
      cors: {
        origin: '*',
        methods: ['GET', 'POST'],
        credentials: true,
      },
      path: '/socket.io',
    });
    expect(mockSetSocketServer).toHaveBeenCalledWith(mockIoServerInstance);

    expect(mockConfigServiceGet).toHaveBeenCalledWith('PORT');
    expect(mockHttpServerListen).toHaveBeenCalledWith(4000); // Default port
    expect(mockLoggerLog).toHaveBeenCalledWith('WebSocket Server is running on port: 4000', 'Bootstrap');
  });

  it('should use PORT from config if available', async () => {
    mockConfigServiceGet.mockImplementation((key: string) => {
      if (key === 'PORT') return 5000;
      return undefined;
    });
    await bootstrap();
    expect(mockHttpServerListen).toHaveBeenCalledWith(5000);
    expect(mockLoggerLog).toHaveBeenCalledWith('WebSocket Server is running on port: 5000', 'Bootstrap');
  });

  it('should use CORS_ORIGIN from config if available', async () => {
    mockConfigServiceGet.mockImplementation((key: string, defaultValue?: any) => {
      if (key === 'CORS_ORIGIN') return 'http://custom.origin';
      if (key === 'PORT') return 4000;
      return defaultValue;
    });
    await bootstrap();
    expect(mockSocketIoServerConstructor).toHaveBeenCalledWith(mockHttpServer, expect.objectContaining({
      cors: expect.objectContaining({ origin: 'http://custom.origin' }),
    }));
  });

  describe('Socket.IO connection events', () => {
    beforeEach(async () => {
      // Ensure bootstrap runs and connection handler is captured and invoked
      await bootstrap();
      if (!capturedConnectionHandler) {
        throw new Error('Socket.IO connection handler not captured');
      }
      // Reset mockSocketOn for fresh handler capture within this connection
      mockSocketOn.mockReset();
      capturedSocketEventHandlers = {}; // Clear previous handlers
      mockSocketOn.mockImplementation((event: string, handler: (data?: any) => void) => {
        capturedSocketEventHandlers[event] = handler;
      });
      
      capturedConnectionHandler(mockClientSocket); // Simulate a client connection
    });

    it('should log client connection', () => {
      expect(mockLoggerLog).toHaveBeenCalledWith(`Client connected: ${mockClientSocket.id}`, 'SocketConnection');
    });

    it('should handle "join_room" event', () => {
      const roomData = { room: 'room123' };
      expect(capturedSocketEventHandlers['join_room']).toBeInstanceOf(Function);
      capturedSocketEventHandlers['join_room'](roomData);
      expect(mockClientSocket.join).toHaveBeenCalledWith('room123');
      expect(mockLoggerLog).toHaveBeenCalledWith(`Client ${mockClientSocket.id} joined room: room123`, 'SocketRoom');
    });

    it('should handle "leave_room" event', () => {
      const roomData = { room: 'room123' };
      expect(capturedSocketEventHandlers['leave_room']).toBeInstanceOf(Function);
      capturedSocketEventHandlers['leave_room'](roomData);
      expect(mockClientSocket.leave).toHaveBeenCalledWith('room123');
      expect(mockLoggerLog).toHaveBeenCalledWith(`Client ${mockClientSocket.id} left room: room123`, 'SocketRoom');
    });

    it('should handle "ping" event and emit "pong"', () => {
      expect(capturedSocketEventHandlers['ping']).toBeInstanceOf(Function);
      capturedSocketEventHandlers['ping']();
      expect(mockClientSocket.emit).toHaveBeenCalledWith('pong');
    });

    it('should handle "disconnect" event', () => {
      expect(capturedSocketEventHandlers['disconnect']).toBeInstanceOf(Function);
      capturedSocketEventHandlers['disconnect']();
      expect(mockLoggerLog).toHaveBeenCalledWith(`Client disconnected: ${mockClientSocket.id}`, 'SocketConnection');
    });

    it('should handle "error" event', () => {
      const testError = new Error('Socket test error');
      expect(capturedSocketEventHandlers['error']).toBeInstanceOf(Function);
      capturedSocketEventHandlers['error'](testError);
      expect(mockLoggerError).toHaveBeenCalledWith(`Socket error for client ${mockClientSocket.id}`, testError, 'SocketError');
    });
  });
});
