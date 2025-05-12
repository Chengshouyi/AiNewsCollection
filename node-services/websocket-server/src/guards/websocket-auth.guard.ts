import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { Socket } from 'socket.io';
import { LoggerService } from '@app/logger';

@Injectable()
export class WebSocketAuthGuard implements CanActivate {
  constructor(
    private readonly jwtService: JwtService,
    private readonly logger: LoggerService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const client = context.switchToWs().getClient<Socket>();
    const token = client.handshake.auth.token;

    try {
      const payload = await this.jwtService.verifyAsync(token);
      client.data.user = payload;
      return true;
    } catch (error) {
      this.logger.error('認證失敗', error);
      return false;
    }
  }
}
