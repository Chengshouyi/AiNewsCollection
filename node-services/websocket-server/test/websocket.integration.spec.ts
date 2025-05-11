import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import { io, Socket } from 'socket.io-client';
import { AppModule } from '../src/app.module';
import { ConfigService } from '@nestjs/config';

describe('WebSocket Integration Tests', () => {
  let app: INestApplication;
  let clientSocket: Socket;
  let configService: ConfigService;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    configService = app.get(ConfigService);
    await app.listen(0);

    const port = app.getHttpServer().address().port;
    clientSocket = io(`http://localhost:${port}`, {
      path: configService.get('WS_PATH'),
      autoConnect: false,
    });
  });

  afterAll(async () => {
    clientSocket.close();
    await app.close();
  });

  it('應該能夠建立 WebSocket 連接', (done) => {
    clientSocket.on('connect', () => {
      expect(clientSocket.connected).toBe(true);
      done();
    });

    clientSocket.connect();
  });

  it('應該能夠加入房間並接收訊息', (done) => {
    clientSocket.on('connect', () => {
      clientSocket.emit('join_room', { room: 'test-room' });
    });

    clientSocket.on('user_joined', (data) => {
      expect(data.room).toBe('test-room');
      done();
    });

    clientSocket.connect();
  });
});
