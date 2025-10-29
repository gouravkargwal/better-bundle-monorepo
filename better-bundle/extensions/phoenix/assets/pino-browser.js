/**
 * Simple Browser Logger for Phoenix Extension
 * Just sends logs to our backend API
 */

// Simple logger for browser
function createPinoLogger(options = {}) {
  const {
    level = 'info',
    base = {},
    transport = null
  } = options;

  const levels = {
    trace: 10,
    debug: 20,
    info: 30,
    warn: 40,
    error: 50,
    fatal: 60
  };

  const currentLevel = levels[level] || levels.info;

  function createLogMethod(levelName, levelNum) {
    return function (obj, msg, ...args) {
      if (levelNum < currentLevel) return;

      const timestamp = new Date().toISOString();
      const logEntry = {
        level: levelNum,
        time: timestamp,
        ...base,
        ...(typeof obj === 'object' && obj !== null ? obj : {}),
        msg: msg || (typeof obj === 'string' ? obj : ''),
        ...(args.length > 0 ? { args } : {})
      };

      // Console output
      const consoleMethod = levelName === 'fatal' ? 'error' : levelName;
      if (console[consoleMethod]) {
        console[consoleMethod](`[${levelName.toUpperCase()}]`, logEntry);
      }

      // Send to transport if available
      if (transport && transport.send) {
        transport.send(logEntry);
      }
    };
  }

  return {
    trace: createLogMethod('trace', levels.trace),
    debug: createLogMethod('debug', levels.debug),
    info: createLogMethod('info', levels.info),
    warn: createLogMethod('warn', levels.warn),
    error: createLogMethod('error', levels.error),
    fatal: createLogMethod('fatal', levels.fatal),
    child: (bindings) => createPinoLogger({
      ...options,
      base: { ...base, ...bindings }
    })
  };
}

// Simple API transport - just sends logs to backend
function createApiTransport(options = {}) {
  const {
    batchSize = 5,
    interval = 3000
  } = options;

  let logBuffer = [];
  let batchTimeout = null;

  function sendLogs() {
    if (logBuffer.length === 0) return;

    const baseUrl = window.getBaseUrl ? window.getBaseUrl() : 'https://nonconscientious-annette-saddeningly.ngrok-free.dev';
    const apiUrl = `${baseUrl}/logs`;

    fetch(apiUrl, {
      method: 'POST',
      mode: 'cors',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        logs: logBuffer,
        source: 'phoenix-extension',
        timestamp: new Date().toISOString()
      })
    })
      .then(response => {
        if (!response.ok) {
          return response.text().then(text => {

          });
        }
        return response.text();
      })
      .then(responseText => {
      })
      .catch(error => {
      });

    logBuffer = [];
  }

  return {
    send: (logEntry) => {
      logBuffer.push(logEntry);

      if (logBuffer.length >= batchSize) {
        sendLogs();
      } else if (!batchTimeout) {
        batchTimeout = setTimeout(() => {
          sendLogs();
          batchTimeout = null;
        }, interval);
      }
    }
  };
}

// Export for global use
window.pino = createPinoLogger;
window.createApiTransport = createApiTransport;

// Create a global logger instance
const globalLogger = createPinoLogger({
  level: 'info',
  base: {
    service: 'phoenix-extension',
    env: 'development'
  },
  transport: createApiTransport({
    batchSize: 5,
    interval: 3000
  })
});

// Make logger available globally
window.phoenixLogger = globalLogger;