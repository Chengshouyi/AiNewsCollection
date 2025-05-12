import { Injectable } from '@nestjs/common';
import { LoggerService } from '@app/logger';
@Injectable()
export class AppService {
  constructor(private readonly logger: LoggerService) {}

  getHello(): string {
    this.logger.log('getHello', AppService.name);
    return 'Hello World!';
  }
}
