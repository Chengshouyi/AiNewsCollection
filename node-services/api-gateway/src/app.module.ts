import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AppService } from './app.service';
import { WebSocketModule } from './websocket/websocket.module';
import { CustomLoggerModule } from '@app/logger';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    CustomLoggerModule.forRootAsync(),
    WebSocketModule,
  ],
  providers: [AppService],
  exports: [AppService]
})
export class AppModule {}
