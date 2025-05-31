# @app/logger

這是一個共享的日誌模組，用於 node-services 專案。

## 功能

- 基於 pino 的高效日誌記錄
- 支援不同日誌級別：trace、debug、info、warn、error、fatal
- 支援 NestJS 框架集成
- 支援自定義服務名稱和日誌格式化

## 安裝

由於這是一個 workspace 包，所以不需要額外安裝。在 node-services 專案中，只需要導入即可使用：

```typescript
import { LoggerService } from '@app/logger';
```

## 用法

### 在 NestJS 應用中使用

```typescript
// app.module.ts
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { CustomLoggerModule } from '@app/logger';

@Module({
  imports: [
    ConfigModule.forRoot(),
    CustomLoggerModule.forRootAsync()
  ],
})
export class AppModule {}
```

### 直接使用 LoggerService

```typescript
import { LoggerService } from '@app/logger';

const logger = new LoggerService({ 
  serviceName: 'MyService',
  level: 'debug',
  prettyPrint: true
});

logger.info('這是一條資訊日誌');
logger.error('發生錯誤', new Error('錯誤詳情'), 'UserController');
```

## 配置選項

- `level`: 日誌級別，預設為 'info'
- `serviceName`: 服務名稱，預設為 'Application'
- `prettyPrint`: 是否美化輸出，在非生產環境預設為 true

## 測試

執行單元測試：

```bash
npm run test
```

查看測試覆蓋率：

```bash
npm run test:cov
```

持續監視模式：

```bash
npm run test:watch
``` 