import pino, { Logger as PinoLogger, DestinationStream } from 'pino';
import dayjs from 'dayjs';

export interface LoggerOptions {
  level?: string;
  serviceName?: string;
  prettyPrint?: boolean; // Typically for development
}

// Define the type for pino log function levels
type PinoLogFnLevel = 'trace' | 'debug' | 'info' | 'warn' | 'error' | 'fatal';

export class LoggerService {
  private pinoLogger: PinoLogger;
  private serviceName: string;

  constructor(options?: LoggerOptions, destination?: DestinationStream) {
    this.serviceName = options?.serviceName || 'Application';

    const logLevel = options?.level || process.env.LOG_LEVEL || 'info';

    let usePrettyPrint: boolean;
    if (options?.prettyPrint !== undefined) {
      usePrettyPrint = options.prettyPrint;
    } else {
      // Default to pretty printing if not in production and not explicitly disabled
      usePrettyPrint = process.env.NODE_ENV !== 'production';
    }

    const pinoOptions: pino.LoggerOptions = {
      level: logLevel,
      base: {
        service: this.serviceName,
      },
      timestamp: () => `,"time":"${dayjs().format()}"`,
      formatters: {
        level: (label) => {
          return { level: label };
        },
      },
    };

    if (usePrettyPrint) {
      // 在測試環境中避免使用 transport 以防止 DataCloneError
      if (process.env.NODE_ENV === 'test') {
        // 在測試環境中使用簡單的格式，不使用 transport
        pinoOptions.transport = undefined;
      } else {
        pinoOptions.transport = {
          target: 'pino-pretty',
          options: {
            colorize: true,
            translateTime: 'SYS:standard',
            ignore: 'pid,hostname,service',
            // 使用字符串模板，避免函數序列化問題
            messageFormat: '{if service}({service}) {end}{if context}[{context}] {end}{msg}'
          },
        };
      }
    }

    this.pinoLogger = pino(pinoOptions, destination);
  }

  // Base logging method
  private doLog(level: PinoLogFnLevel, message: string, context?: string, objOrError?: any) {
    const logObject: { context?: string; err?: Error; [key: string]: any } = {};
    if (context) {
      logObject.context = context;
    }

    if (objOrError instanceof Error) {
      logObject.err = objOrError; // pino has special handling for 'err'
    } else if (typeof objOrError === 'object' && objOrError !== null) {
      Object.assign(logObject, objOrError);
    } else if (objOrError !== undefined) {
      logObject.data = objOrError; // if it's not an error and not an object, log as data
    }

    this.pinoLogger[level](logObject, message);
  }

  log(message: string, context?: string, data?: any) {
    this.doLog('info', message, context, data);
  }

  info(message: string, context?: string, data?: any) {
    this.doLog('info', message, context, data);
  }

  error(message: string, traceOrError?: string | Error, context?: string, data?: any) {
    let errorObj: Error | undefined;
    let trace: string | undefined;

    if (traceOrError instanceof Error) {
      errorObj = traceOrError;
      if (typeof context === 'object' && context !== null && data === undefined) {
        data = context;
        context = undefined;
      }
    } else if (typeof traceOrError === 'string' && (traceOrError.includes('\\n') || typeof context !== 'string') ) {
      // If traceOrError is a string and looks like a stack, or context isn't a string, assume traceOrError is a trace.
      trace = traceOrError;
      errorObj = new Error(message); // Create a synthetic error for the trace
      errorObj.stack = trace;
       if (typeof context === 'object' && context !== null && data === undefined) { // error(message, trace, data)
        data = context;
        context = undefined;
      }
      // if context is string, it's error(message, trace, context)
      // if context is undefined, it's error(message, trace)
    } else if (typeof traceOrError === 'object' && traceOrError !== null) {
      // Handles: error(message, data, context?)
      // Here, traceOrError (second param) is data.
      // The 'context' variable (third param) is the actual context.
      data = traceOrError;
      traceOrError = undefined; // Clear this as it's been processed as data.
    } else if (typeof traceOrError === 'string') {
        // Handles: error(message, contextFromTraceOrErrorSlot, dataFromContextSlot?)
        // This case means traceOrError was a string, but not a stack trace. So it's context.
        data = context; // original context (3rd param) is now data
        context = traceOrError; // traceOrError (2nd param) is context
        traceOrError = undefined;
    }
    // If traceOrError was undefined from the start, then 'context' is context and 'data' is data.

    const logPayload = { ...data }; // Initialize with data
    if (trace) {
        logPayload.stack = trace;
    }
    this.doLog('error', message, context, errorObj || logPayload);
  }

  warn(message: string, context?: string, data?: any) {
    this.doLog('warn', message, context, data);
  }

  debug(message: string, context?: string, data?: any) {
    this.doLog('debug', message, context, data);
  }

  verbose(message: string, context?: string, data?: any) {
    // Pino uses 'trace' for verbose. You can map it if you prefer 'verbose'.
    this.doLog('trace', message, context, data);
  }

  // For NestJS compatibility (implementing LoggerService interface from @nestjs/common)
  getNestLogger() {
    return {
        log: (message: any, contextOrData?: string | any, optionalContext?: string) => {
            if (typeof contextOrData === 'string') {
                this.log(message, contextOrData); // Standard Nest log(message, context)
            } else if (typeof contextOrData === 'object') {
                // Custom: log(message, data, context)
                this.log(message, optionalContext, contextOrData);
            } else {
                this.log(message);
            }
        },
        error: (message: any, traceOrErrorOrData?: string | Error | any, contextOrData?: string | any, optionalContext?: string) => {
            if (traceOrErrorOrData instanceof Error) {
                // error(message, Error, context?) or error(message, Error, data?, context?)
                if (typeof contextOrData === 'string' && optionalContext === undefined) { // Nest: error(message, Error, context)
                    this.error(message, traceOrErrorOrData, contextOrData);
                } else { // Nest: error(message, Error, data, context) -> our error(message, Error, context, data)
                    this.error(message, traceOrErrorOrData, optionalContext, contextOrData);
                }
            } else if (typeof traceOrErrorOrData === 'string' && (traceOrErrorOrData.includes('\\n') || (typeof contextOrData !== 'string' && contextOrData !== undefined))) {
                // traceOrErrorOrData is a string.
                // If it contains a newline, it's a stack trace.
                // OR, if contextOrData is NOT a string (e.g. it's data (an object) or undefined), then traceOrErrorOrData must be a trace.
                // Nest: error(message, trace, context?) or error(message, trace, data?)
                if(typeof contextOrData === 'string'){ // error(message, trace, context)
                     this.error(message, traceOrErrorOrData, contextOrData);
                } else { // error(message, trace, data_in_contextOrData_slot)
                     this.error(message, traceOrErrorOrData, undefined, contextOrData);
                }
            } else if (typeof traceOrErrorOrData === 'object' && traceOrErrorOrData !== null ) { // Nest: error(message, data, context?)
                this.error(message, undefined, contextOrData as string | undefined, traceOrErrorOrData);
            } else if (typeof traceOrErrorOrData === 'string') { // Nest: error(message, context)
                this.error(message, undefined, traceOrErrorOrData);
            }
            else { // Nest: error(message)
                this.error(message);
            }
        },
        warn: (message: any, contextOrData?: string | any, optionalContext?: string) => {
              if (typeof contextOrData === 'string') {
                this.warn(message, contextOrData);
            } else if (typeof contextOrData === 'object') {
                this.warn(message, optionalContext, contextOrData);
            } else {
                this.warn(message);
            }
        },
        debug: (message: any, contextOrData?: string | any, optionalContext?: string) => {
            if (typeof contextOrData === 'string') {
                this.debug(message, contextOrData);
            } else if (typeof contextOrData === 'object') {
                this.debug(message, optionalContext, contextOrData);
            } else {
                this.debug(message);
            }
        },
        verbose: (message: any, contextOrData?: string | any, optionalContext?: string) => {
            if (typeof contextOrData === 'string') {
                this.verbose(message, contextOrData);
            } else if (typeof contextOrData === 'object') {
                this.verbose(message, optionalContext, contextOrData);
            } else {
                this.verbose(message);
            }
        },
        // If you need to set log levels dynamically for NestJS
        // setLogLevels: (levels: LogLevel[]) => { /* ... */ }
    };
  }
} 