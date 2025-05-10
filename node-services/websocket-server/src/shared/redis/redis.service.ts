import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private client: Redis.Redis;
  private subscriber: Redis.Redis;

  constructor(private readonly configService: ConfigService) {}

  onModuleInit() {
    const redisUrl = this.configService.get<string>('REDIS_URL', 'redis://localhost:6379');
    this.client = new Redis(redisUrl);
    this.subscriber = new Redis(redisUrl);
  }

  onModuleDestroy() {
    this.client?.disconnect();
    this.subscriber?.disconnect();
  }

  // 發布訊息
  async publish(channel: string, message: any) {
    await this.client.publish(channel, JSON.stringify(message));
  }

  // 訂閱訊息
  subscribe(channel: string, handler: (message: any) => void) {
    this.subscriber.subscribe(channel, (err, count) => {
      if (err) {
        this.logger.error(`Redis 訂閱失敗: ${err}`);
      } else {
        this.logger.log(`Redis 已訂閱 ${channel} 頻道`);
      }
    });

    this.subscriber.on('message', (chan, message) => {
      if (chan === channel) {
        try {
          handler(JSON.parse(message));
        } catch (e) {
          this.logger.warn(`Redis 訊息解析失敗: ${e}`);
          handler(message);
        }
      }
    });
  }
}
