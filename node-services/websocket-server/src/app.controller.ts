import { Controller, Logger, Get } from '@nestjs/common';
import { AppService } from './app.service';
import { LoggerService } from '@app/logger';

@Controller()
export class AppController {

  constructor(private readonly appService: AppService, private readonly logger: LoggerService) {}

  @Get()
  getHello(): string {
    this.logger.log('getHello', AppController.name);
    return this.appService.getHello();
  }
}
