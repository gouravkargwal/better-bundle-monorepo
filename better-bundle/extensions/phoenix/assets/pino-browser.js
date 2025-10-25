/**
 * Pino Browser Implementation for Phoenix Extension
 * Custom browser-compatible Pino logger with Loki transport
 */

// Simple Pino-compatible logger for browser
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

// Loki transport for browser
function createLokiTransport(options = {}) {
  const {
    host = 'https://nonconscientious-annette-saddeningly.ngrok-free.dev:3100',
    labels = {},
    batchSize = 10,
    interval = 5000
  } = options;

  // Test connectivity to Loki
  console.log('🔍 Testing Loki connectivity to:', host);

  // First, test if the ngrok URL is reachable at all
  fetch(`${host}`, {
    method: 'GET',
    mode: 'no-cors' // Try without CORS first
  })
    .then(response => {
      console.log('✅ ngrok URL is reachable (no-cors):', response.type);
    })
    .catch(error => {
      console.error('❌ ngrok URL not reachable (no-cors):', error);
    });

  // Then test the Loki endpoint
  fetch(`${host}/ready`, {
    method: 'GET',
    mode: 'cors',
    headers: {
      'Accept': 'application/json'
    }
  })
    .then(response => {
      console.log('✅ Loki is reachable:', response.status, response.statusText);
      return response.text();
    })
    .then(text => {
      console.log('📄 Loki response body:', text);
    })
    .catch(error => {
      console.error('❌ Loki connectivity test failed:', error);
      console.error('❌ Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
    });

  let logBuffer = [];
  let batchTimeout = null;

  function sendBatch() {
    if (logBuffer.length === 0) return;

    const payload = {
      streams: [{
        stream: labels,
        values: logBuffer.map(log => [
          (new Date(log.time).getTime() * 1000000).toString(), // nanoseconds
          JSON.stringify(log)
        ])
      }]
    };

    console.log('🚀 Sending logs to Loki:', {
      url: `${host}/loki/api/v1/push`,
      payload: payload,
      logCount: logBuffer.length
    });

    // Add timeout to fetch request
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    fetch(`${host}/loki/api/v1/push`, {
      method: 'POST',
      mode: 'cors',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
      .then(response => {
        clearTimeout(timeoutId);
        console.log('📊 Loki response status:', response.status, response.statusText);
        if (!response.ok) {
          return response.text().then(text => {
            console.error('❌ Loki error response:', text);
            throw new Error(`Loki error: ${response.status} ${text}`);
          });
        }
        return response.text();
      })
      .then(responseText => {
        console.log('✅ Loki success response:', responseText);
      })
      .catch(error => {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          console.error('⏰ Loki request timed out after 10 seconds');
        } else {
          console.error('❌ Failed to send logs to Loki:', error);
        }
      });

    logBuffer = [];
  }

  return {
    send: (logEntry) => {
      console.log('📝 Loki transport received log:', logEntry);
      logBuffer.push(logEntry);

      if (logBuffer.length >= batchSize) {
        console.log('📦 Batch size reached, sending immediately');
        sendBatch();
      } else if (!batchTimeout) {
        console.log('⏰ Setting batch timeout for', interval, 'ms');
        batchTimeout = setTimeout(() => {
          console.log('⏰ Batch timeout reached, sending logs');
          sendBatch();
          batchTimeout = null;
        }, interval);
      }
    }
  };
}

// Export for global use
window.pino = createPinoLogger;
window.createLokiTransport = createLokiTransport;
