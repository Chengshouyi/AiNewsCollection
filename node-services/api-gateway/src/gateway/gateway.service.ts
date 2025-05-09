import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class GatewayService {
  constructor(private configService: ConfigService) {}

  getStatus() {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'api-gateway',
      pythonBackendUrl: this.configService.get<string>('PYTHON_BACKEND_URL')
    };
  }
} 