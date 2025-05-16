import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { ClientsModule, Transport } from '@nestjs/microservices';
import { GatewayController } from './gateway.controller';

@Module({
  imports: [
    HttpModule,
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    ClientsModule.register([
      {
        name: 'WEBSOCKET_SERVICE',
        transport: Transport.TCP,
        options: {
          host: process.env.WEBSOCKET_SERVICE_HOST || 'localhost',
          port: parseInt(process.env.WEBSOCKET_SERVICE_PORT || '3001', 10),
        },
      },
    ]),
  ],
  controllers: [GatewayController],
})
export class GatewayModule {}
