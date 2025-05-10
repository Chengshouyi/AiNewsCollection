import { Module } from '@nestjs/common';
import { TasksGateway } from './tasks.gateway';

@Module({
  providers: [TasksGateway],
  exports: [TasksGateway],
})
export class TasksModule {}
