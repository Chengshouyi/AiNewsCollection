import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private client: Redis;
  private subscriber: Redis;

  constructor(private readonly configService: ConfigService) {}

  async onModuleInit() {
    const redisUrl = this.configService.get<string>('REDIS_URL', 'redis://localhost:6379');
    this.logger.log(`Connecting to Redis at ${redisUrl}`);
    this.client = new Redis(redisUrl);
    this.subscriber = new Redis(redisUrl);

    this.client.on('connect', () => this.logger.log('Redis client connected'));
    this.client.on('error', (err) => this.logger.error('Redis client error', err));
    this.subscriber.on('connect', () => this.logger.log('Redis subscriber connected'));
    this.subscriber.on('error', (err) => this.logger.error('Redis subscriber error', err));
  }

  async onModuleDestroy() {
    await this.client?.quit();
    await this.subscriber?.quit();
    this.logger.log('Redis connections closed');
  }

  getClient(): Redis {
    return this.client;
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
