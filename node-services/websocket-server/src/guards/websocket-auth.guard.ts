import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { Socket } from 'socket.io';
import { LoggerService } from '@app/logger';

interface JwtPayload {
  sub: string;
  username: string;
}

interface AuthenticatedSocket extends Socket {
  data: {
    user?: JwtPayload;
  };
}

@Injectable()
export class WebSocketAuthGuard implements CanActivate {
  constructor(
    private readonly jwtService: JwtService,
    private readonly logger: LoggerService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    const token = client.handshake.auth.token as string;

    try {
      const payload = await this.jwtService.verifyAsync<JwtPayload>(token);
      client.data.user = payload;
      return true;
    } catch (error) {
      this.logger.error('認證失敗', error as Error, 'WebSocketAuthGuard');
      return false;
    }
  }
}
