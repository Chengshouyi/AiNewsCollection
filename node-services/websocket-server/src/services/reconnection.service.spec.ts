import { Test, TestingModule } from '@nestjs/testing';
import { ReconnectionService } from './reconnection.service';
import { Socket } from 'socket.io';

// 測試專用類型定義，用於訪問私有成員
interface ReconnectionServiceTestAccess {
  reconnectAttempts: Map<string, number>;
  delayReconnection: (socket: Socket, attempt: number) => Promise<void>;
}

describe('ReconnectionService', () => {
  let service: ReconnectionService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [ReconnectionService],
    }).compile();

    service = module.get<ReconnectionService>(ReconnectionService);
  });

  it('應該被定義', () => {
    expect(service).toBeDefined();
  });

  describe('handleReconnection', () => {
    it('當重連次數未達上限時應該增加次數並延遲', async () => {
      const mockSocket: Partial<Socket> = {
        id: 'socket-1',
        connected: false,
      };
      const serviceWithAccess = service as ReconnectionService &
        ReconnectionServiceTestAccess;
      const delaySpy = jest
        .spyOn(serviceWithAccess, 'delayReconnection' as any)
        .mockResolvedValue(undefined as never);
      await service.handleReconnection(mockSocket as Socket);
      expect(serviceWithAccess.reconnectAttempts.get('socket-1')).toBe(1);
      expect(delaySpy).toHaveBeenCalledWith(mockSocket, 0);
      delaySpy.mockRestore();
    });

    it('當重連次數達到上限時不應該再增加', async () => {
      const mockSocket: Partial<Socket> = {
        id: 'socket-2',
        connected: false,
      };
      const serviceWithAccess = service as ReconnectionService &
        ReconnectionServiceTestAccess;
      serviceWithAccess.reconnectAttempts.set('socket-2', 5);
      const delaySpy = jest.spyOn(
        serviceWithAccess,
        'delayReconnection' as any,
      );
      await service.handleReconnection(mockSocket as Socket);
      expect(delaySpy).not.toHaveBeenCalled();
      expect(serviceWithAccess.reconnectAttempts.get('socket-2')).toBe(5);
      delaySpy.mockRestore();
    });
  });

  describe('delayReconnection', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });
    afterEach(() => {
      jest.useRealTimers();
    });

    it('應該根據次數延遲正確的時間', async () => {
      const mockSocket: Partial<Socket> = {
        id: 'socket-3',
        connected: false,
      };
      const serviceWithAccess = service as ReconnectionService &
        ReconnectionServiceTestAccess;
      const promise = serviceWithAccess.delayReconnection(mockSocket as Socket, 2);
      jest.advanceTimersByTime(1000 * 3);
      await promise;
    });

    it('當 socket 已連線時應該移除重連次數紀錄', async () => {
      const mockSocket: Partial<Socket> = {
        id: 'socket-4',
        connected: true,
      };
      const serviceWithAccess = service as ReconnectionService &
        ReconnectionServiceTestAccess;
      serviceWithAccess.reconnectAttempts.set('socket-4', 2);
      const promise = serviceWithAccess.delayReconnection(mockSocket as Socket, 2);
      jest.runAllTimers();
      await promise;
      expect(serviceWithAccess.reconnectAttempts.has('socket-4')).toBe(false);
    });

    it('當 socket 未連線時不應該移除重連次數紀錄', async () => {
      const mockSocket: Partial<Socket> = {
        id: 'socket-5',
        connected: false,
      };
      const serviceWithAccess = service as ReconnectionService &
        ReconnectionServiceTestAccess;
      serviceWithAccess.reconnectAttempts.set('socket-5', 2);
      const promise = serviceWithAccess.delayReconnection(mockSocket as Socket, 2);
      jest.runAllTimers();
      await promise;
      expect(serviceWithAccess.reconnectAttempts.has('socket-5')).toBe(true);
    });
  });
});
