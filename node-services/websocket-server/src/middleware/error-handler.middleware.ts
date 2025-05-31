import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { LoggerService } from '@app/logger';

@Injectable()
export class ErrorHandlerMiddleware implements NestMiddleware {
  constructor(private readonly logger: LoggerService) {}

  use(req: Request, res: Response, next: NextFunction) {
    try {
      next();
    } catch (error: unknown) {
      this.logger.error('WebSocket 錯誤', error as Error);
      res.status(500).json({
        statusCode: 500,
        message: '內部伺服器錯誤',
        error: error instanceof Error ? error.message : '未知錯誤',
      });
    }
  }
}
