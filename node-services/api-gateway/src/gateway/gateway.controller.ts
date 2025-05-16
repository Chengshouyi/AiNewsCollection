import {
  All,
  Controller,
  Req,
  Res,
  Param,
  Query,
  Body,
  Headers,
  Logger,
  Inject,
} from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { Request, Response } from 'express';
import { AxiosRequestConfig, Method } from 'axios';
import { firstValueFrom } from 'rxjs';
import { ApiOperation, ApiParam, ApiTags } from '@nestjs/swagger';
import { ClientProxy } from '@nestjs/microservices';
import { LoggerService } from '@app/logger';

@ApiTags('Backend Gateway')
@Controller() // You can add a prefix if needed, e.g., @Controller('proxy')
export class GatewayController {
  private readonly PYTHON_BACKEND_URL: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject('WEBSOCKET_SERVICE') private readonly websocketClient: ClientProxy,
    private readonly logger: LoggerService,
  ) {
    const backendUrl = this.configService.get<string>(
      'PYTHON_BACKEND_URL',
    );
    if (!backendUrl) {
      this.logger.error('PYTHON_BACKEND_URL is not defined in environment variables', GatewayController.name);
      throw new Error('PYTHON_BACKEND_URL is not defined in environment variables');
    }
    this.PYTHON_BACKEND_URL = backendUrl;
  }

  @All('*path')
  @ApiOperation({
    summary: 'Generic Backend Proxy Route',
    description: `
      This route forwards all requests to the configured PYTHON_BACKEND_URL.
      It supports all HTTP methods (GET, POST, PUT, DELETE, etc.).
      Request path, query parameters, headers, and body are forwarded.
      The response from the backend service (status code, headers, body) is returned to the client.
      For detailed API endpoint definitions, please refer to the backend service's OpenAPI documentation.
    `,
  })
  @ApiParam({
    name: 'path',
    type: String,
    required: false,
    description: 'The path to be forwarded to the backend service',
  })
  async handleAllRequests(
    @Param('path') forwardPath: string,
    @Req() req: Request,
    @Res() res: Response,
    @Query() query: Record<string, any>,
    // @Body() body: any, // req.body already contains the parsed body
    // @Headers() headers: Record<string, string>, // req.headers is more complete
  ) {
    const { method, headers: originalHeaders, body } = req;

    // 處理OPTIONS請求（CORS預檢請求）
    if (method === 'OPTIONS') {
      res.status(204).end();
      return;
    }

    // forwardPath should now directly contain the path segment matched by '*path'
    
    const targetUrl = `${this.PYTHON_BACKEND_URL}/${forwardPath}`;

    this.logger.log(
      `Forwarding request: ${method} ${targetUrl} query: ${JSON.stringify(query)}`,
      GatewayController.name,
    );

    // 處理請求頭
    const headersToForward = { ...originalHeaders };
    
    // 移除不應轉發的請求頭
    const headersToRemove = [
      'host', 
      'connection', 
      'origin', 
      'referer', 
      'sec-fetch-site', 
      'sec-fetch-mode', 
      'sec-fetch-dest'
    ];
    
    headersToRemove.forEach(header => {
      delete headersToForward[header];
    });
    
    // 添加必要的請求頭
    headersToForward['x-forwarded-for'] = req.ip;
    headersToForward['x-forwarded-proto'] = req.protocol;
    headersToForward['x-forwarded-host'] = req.get('host');

    const axiosConfig: AxiosRequestConfig = {
      method: method as Method,
      url: targetUrl,
      params: query,
      data: body,
      headers: headersToForward,
      validateStatus: function (status) {
        this.logger.log(`validateStatus: ${status}`, GatewayController.name);
        return status >= 200 && status < 600; // Handle all status codes from backend
      },
    };

    try {
      const backendResponse = await firstValueFrom(
        this.httpService.request(axiosConfig),
      );

      // 處理 WebSocket 通知
      if (backendResponse.status === 200 || backendResponse.status === 201) {
        // 檢查是否需要發送 WebSocket 通知
        if (this.shouldEmitWebSocketEvent(forwardPath, method, backendResponse.data)) {
          this.logger.log(`shouldEmitWebSocketEvent: ${forwardPath} ${method} ${backendResponse.data}`, GatewayController.name);
          await this.emitWebSocketEvent(forwardPath, method, backendResponse.data);
        }
      }

      // 處理響應頭
      const responseHeaders = backendResponse.headers;
      const headersToSkip = ['transfer-encoding', 'connection', 'content-length'];
      
      Object.keys(responseHeaders).forEach((key) => {
        const lowerKey = key.toLowerCase();
        if (!headersToSkip.includes(lowerKey)) {
          this.logger.log(`setHeader: ${key} ${responseHeaders[key]}`, GatewayController.name);
          res.setHeader(key, responseHeaders[key]);
        }
      });

      this.logger.log(`sendResponse: ${backendResponse.status} ${backendResponse.data}`, GatewayController.name);
      res.status(backendResponse.status).send(backendResponse.data);

    } catch (error) {
      this.logger.error(`Error forwarding request to ${targetUrl}: ${error.message}`, GatewayController.name);
      if (error.response) {
        // 處理錯誤響應頭
        const errorHeaders = error.response.headers;
        const headersToSkip = ['transfer-encoding', 'connection', 'content-length'];
        
        Object.keys(errorHeaders).forEach((key) => {
          const lowerKey = key.toLowerCase();
          if (!headersToSkip.includes(lowerKey)) {
            this.logger.log(`setHeader: ${key} ${errorHeaders[key]}`, GatewayController.name);
            res.setHeader(key, errorHeaders[key]);
          }
        });
        
        this.logger.log(`sendResponse: ${error.response.status} ${error.response.data}`, GatewayController.name);
        res.status(error.response.status).send(error.response.data);
      } else if (error.request) {
        this.logger.log(`sendResponse: 504 Gateway Timeout`, GatewayController.name);
        res.status(504).json({
          statusCode: 504,
          message: 'Gateway Timeout: No response from upstream server.',
          error: 'Gateway Timeout',
        });
      } else {
        this.logger.log(`sendResponse: 502 Bad Gateway`, GatewayController.name);
        res.status(502).json({
          statusCode: 502,
          message: 'Bad Gateway: Error in setting up proxy request.',
          error: 'Bad Gateway',
        });
      }
    }
  }

  // 判斷是否需要發送 WebSocket 事件
  private shouldEmitWebSocketEvent(path: string, method: string, data: any): boolean {
    this.logger.log(`shouldEmitWebSocketEvent: ${path} ${method} ${JSON.stringify(data)}`, GatewayController.name);
    
    // 確保 data 是對象
    const dataObj = typeof data === 'string' ? JSON.parse(data) : data;
    
    // 添加詳細的條件檢查日誌
    const isTaskPath = path.startsWith('tasks/');
    const isPostMethod = method === 'POST';
    const hasData = !!dataObj;
    const hasSuccess = dataObj?.success === true;
    
    this.logger.log(
      `shouldEmitWebSocketEvent conditions: ${JSON.stringify({
        path,
        method,
        isTaskPath,
        isPostMethod,
        hasData,
        hasSuccess,
        dataObj,
      })}`,
      GatewayController.name
    );
    
    if (isTaskPath && isPostMethod && hasData && hasSuccess) {
      this.logger.log(`shouldEmitWebSocketEvent is true: ${path} ${method} ${JSON.stringify(dataObj)}`, GatewayController.name);
      return true;
    }
    
    this.logger.log(`shouldEmitWebSocketEvent is false: ${path} ${method} ${JSON.stringify(dataObj)}`, GatewayController.name);
    return false;
  }

  // 發送 WebSocket 事件
  private async emitWebSocketEvent(path: string, method: string, data: any) {
    try {
      const taskId = data.data?.task_id;
      if (taskId) {
        const room = `task_${taskId}`;
        this.logger.log(`emitWebSocketEvent: ${room} ${method} ${JSON.stringify(data)}`, GatewayController.name);
        await firstValueFrom(
          this.websocketClient.emit('task_progress', {
            room,
            event: 'task_progress',
            data: {
              task_id: taskId,
              status: data.status || 'COMPLETED',
              progress: data.progress || 100,
              message: data.message || '任務已完成',
              timestamp: new Date()
            }
          })
        );
      }
    } catch (error) {
      this.logger.error('Error emitting WebSocket event:', error, GatewayController.name);
    }
  }
} 