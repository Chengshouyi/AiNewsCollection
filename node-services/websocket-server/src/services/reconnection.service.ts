import { Injectable } from '@nestjs/common';
import { Socket } from 'socket.io';

@Injectable()
export class ReconnectionService {
  private readonly reconnectAttempts = new Map<string, number>();
  private readonly maxAttempts = 5;
  private readonly delay = 1000;

  async handleReconnection(socket: Socket) {
    const attempts = this.reconnectAttempts.get(socket.id) || 0;
    if (attempts < this.maxAttempts) {
      this.reconnectAttempts.set(socket.id, attempts + 1);
      await this.delayReconnection(socket, attempts);
    }
  }

  private async delayReconnection(socket: Socket, attempts: number) {
    await new Promise((resolve) =>
      setTimeout(resolve, this.delay * (attempts + 1)),
    );
    if (socket.connected) {
      this.reconnectAttempts.delete(socket.id);
    }
  }
}
