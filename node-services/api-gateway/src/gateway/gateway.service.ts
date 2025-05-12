import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { LoggerService } from '@app/logger';

@Injectable()
export class GatewayService {
  constructor(private configService: ConfigService, private logger: LoggerService) {}

  getStatus() {
    this.logger.log('getStatus', GatewayService.name);
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'api-gateway',
      pythonBackendUrl: this.configService.get<string>('PYTHON_BACKEND_URL')
    };
  }
} 