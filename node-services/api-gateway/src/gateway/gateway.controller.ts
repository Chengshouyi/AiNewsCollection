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

@ApiTags('Backend Gateway')
@Controller() // You can add a prefix if needed, e.g., @Controller('proxy')
export class GatewayController {
  private readonly logger = new Logger(GatewayController.name);
  private readonly PYTHON_BACKEND_URL: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject('WEBSOCKET_SERVICE') private readonly websocketClient: ClientProxy,
  ) {
    const backendUrl = this.configService.get<string>(
      'PYTHON_BACKEND_URL',
    );
    if (!backendUrl) {
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

    // forwardPath should now directly contain the path segment matched by '*path'
    
    const targetUrl = `${this.PYTHON_BACKEND_URL}/${forwardPath}`;

    this.logger.log(
      `Forwarding request: ${method} ${targetUrl} query: ${JSON.stringify(query)}`,
    );

    const headersToForward = { ...originalHeaders };
    delete headersToForward['host'];
    delete headersToForward['connection'];

    const axiosConfig: AxiosRequestConfig = {
      method: method as Method,
      url: targetUrl,
      params: query,
      data: body,
      headers: headersToForward,
      validateStatus: function (status) {
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
          await this.emitWebSocketEvent(forwardPath, method, backendResponse.data);
        }
      }

      Object.keys(backendResponse.headers).forEach((key) => {
        if (key.toLowerCase() !== 'transfer-encoding' && key.toLowerCase() !== 'connection') {
           res.setHeader(key, backendResponse.headers[key]);
        }
      });
      
      res.status(backendResponse.status).send(backendResponse.data);

    } catch (error) {
      this.logger.error(`Error forwarding request to ${targetUrl}: ${error.message}`);
      if (error.response) {
        Object.keys(error.response.headers).forEach((key) => {
          if (key.toLowerCase() !== 'transfer-encoding' && key.toLowerCase() !== 'connection') {
            res.setHeader(key, error.response.headers[key]);
          }
        });
        res.status(error.response.status).send(error.response.data);
      } else if (error.request) {
        res.status(504).json({
          statusCode: 504,
          message: 'Gateway Timeout: No response from upstream server.',
          error: 'Gateway Timeout',
        });
      } else {
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
    // 例如：當任務完成時發送通知
    if (path.includes('/tasks/') && method === 'POST' && data.success) {
      return true;
    }
    return false;
  }

  // 發送 WebSocket 事件
  private async emitWebSocketEvent(path: string, method: string, data: any) {
    try {
      if (path.includes('/tasks/')) {
        const taskId = data.data?.task_id;
        if (taskId) {
          const room = `task_${taskId}`;
          await this.websocketClient.emit('task_progress', {
            room,
            event: 'task_progress',
            data: {
              task_id: taskId,
              status: data.status || 'COMPLETED',
              progress: data.progress || 100,
              message: data.message || '任務已完成',
              timestamp: new Date()
            }
          }).toPromise();
        }
      }
    } catch (error) {
      this.logger.error('Error emitting WebSocket event:', error);
    }
  }
} 