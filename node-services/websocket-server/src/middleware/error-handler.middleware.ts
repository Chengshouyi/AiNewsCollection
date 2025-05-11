@Injectable()
export class ErrorHandlerMiddleware implements NestMiddleware {
  constructor(private readonly logger: LoggerService) {}

  use(req: Request, res: Response, next: Function) {
    try {
      next();
    } catch (error) {
      this.logger.error('WebSocket 錯誤', error);
      res.status(500).json({
        statusCode: 500,
        message: '內部伺服器錯誤',
        error: error.message,
      });
    }
  }
}
