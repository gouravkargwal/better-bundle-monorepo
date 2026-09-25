import { NodeSDK } from "@opentelemetry/sdk-node";
import { logs } from "@opentelemetry/api-logs";
import { context } from "@opentelemetry/api";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { PeriodicExportingMetricReader } from "@opentelemetry/sdk-metrics";
import { Resource } from "@opentelemetry/resources";
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_DEPLOYMENT_ENVIRONMENT_NAME,
} from "@opentelemetry/semantic-conventions";
import { BatchLogRecordProcessor } from "@opentelemetry/sdk-logs";
import { PinoInstrumentation } from "@opentelemetry/instrumentation-pino";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";
import { ExpressInstrumentation } from "@opentelemetry/instrumentation-express";

let sdk: NodeSDK | null = null;

// console level -> OTel severity. SeverityNumber values are from the spec:
// DEBUG=5, INFO=9, WARN=13, ERROR=17.
const CONSOLE_LEVELS: Array<[keyof Console, number, string]> = [
  ["debug", 5, "DEBUG"],
  ["info", 9, "INFO"],
  ["log", 9, "INFO"],
  ["warn", 13, "WARN"],
  ["error", 17, "ERROR"],
];

// Only the first frame is ever read, but V8 needs a frame or two of headroom
// to fill it reliably. Kept low deliberately: the stack is captured on EVERY
// bridged console call, and the cost of a capture scales with this number.
const CALLSITE_FRAME_LIMIT = 3;

// V8 frame, both shapes:  "    at fn (/app/routes/x.tsx:12:5)"
//                         "    at /app/routes/x.tsx:12:5"
const FRAME = /^\s*at (?:(.+?) \()?(?:async )?(.+?):(\d+):\d+\)?$/;

/**
 * Attributes naming the application code that called console.*.
 *
 * Without this every log line from this service arrives under
 * `instrumentation_library_name: "console"`, because the bridge below is a
 * single OTel logger — you can tell the record came from remix-app, but not
 * which route or module wrote it, which is the first question you ask of an
 * error. The names match what the Python worker's LoggingHandler already
 * emits (`code.filepath`, `code.lineno`, `code.function`), so the column is
 * the same one in OpenObserve for both services.
 */
export function callSite(boundary: (...a: unknown[]) => void): Record<string, string | number> {
  const previousLimit = Error.stackTraceLimit;
  try {
    Error.stackTraceLimit = CALLSITE_FRAME_LIMIT;
    const holder: { stack?: string } = {};
    if (typeof Error.captureStackTrace === "function") {
      // Drops every frame up to and including `boundary`, so frame 0 is the
      // caller rather than this file's own wrapper.
      Error.captureStackTrace(holder, boundary);
    } else {
      holder.stack = new Error().stack; // non-V8: filtered below instead
    }

    for (const line of (holder.stack ?? "").split("\n").slice(1)) {
      const m = FRAME.exec(line);
      if (!m) continue;
      const [, fn, file, lineNo] = m;
      // Guard for the non-V8 path, where our own frames are still present.
      if (file.includes("otel-logger")) continue;
      const attrs: Record<string, string | number> = {
        "code.filepath": file.replace(/^file:\/\//, ""),
        "code.lineno": Number(lineNo),
      };
      if (fn) attrs["code.function"] = fn;
      return attrs;
    }
    return {};
  } catch {
    return {}; // a logger that throws while logging takes the request with it
  } finally {
    Error.stackTraceLimit = previousLimit;
  }
}

// Exported for tests; the guard below makes repeat calls a no-op.
export let consoleBridged = false;

/**
 * Forward console.* to the OpenTelemetry log pipeline, keeping the original
 * console behaviour intact so local terminal output is unchanged.
 *
 * Emitting inside the active span's context is what lets a log line be clicked
 * through from its trace: OpenObserve correlates on trace_id/span_id, and a log
 * record created outside a span carries neither.
 */
export function bridgeConsole(): void {
  if (consoleBridged) return;
  consoleBridged = true;
  const otelLogger = logs.getLogger("console");

  for (const [method, severityNumber, severityText] of CONSOLE_LEVELS) {
    const original = (console[method] as (...a: unknown[]) => void).bind(console);
    const bridged = (...args: unknown[]) => {
      original(...args);
      try {
        otelLogger.emit({
          severityNumber,
          severityText,
          body: args
            .map((a) =>
              typeof a === "string"
                ? a
                : a instanceof Error
                  ? `${a.message}\n${a.stack ?? ""}`
                  : safeStringify(a),
            )
            .join(" "),
          // `bridged` is the boundary: frames at or above it are this file's
          // own plumbing, so the first frame below it is the real call site.
          attributes: callSite(bridged),
          context: context.active(),
        });
      } catch {
        // A logger that throws while logging takes the request with it. The
        // original console call above has already run, so the line is not lost.
      }
    };
    (console as unknown as Record<string, unknown>)[method] = bridged;
  }
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value) ?? String(value);
  } catch {
    return String(value); // circular structures, BigInt, etc.
  }
}

export function initObservability(): NodeSDK {
  if (sdk) return sdk;

  const endpoint = process.env.OPENOBSERVE_ENDPOINT || "http://localhost:5080";
  const org = process.env.OPENOBSERVE_ORG || "default";
  const apiKey = process.env.OPENOBSERVE_API_KEY || "";

  sdk = new NodeSDK({
    resource: new Resource({
      [ATTR_SERVICE_NAME]: "remix-app",
      [ATTR_SERVICE_VERSION]: "1.0.0",
      [ATTR_DEPLOYMENT_ENVIRONMENT_NAME]: process.env.NODE_ENV || "development",
    }),
    // Batched, not Simple. SimpleLogRecordProcessor issues one HTTP POST per
    // log record, on the request path: a storefront page that logs five lines
    // pays five round trips to OpenObserve before it can respond. Batching
    // trades a few seconds of delivery latency for that, which is the right
    // trade for every log line this app writes.
    logRecordProcessor: new BatchLogRecordProcessor(
      new OTLPLogExporter({
        // `/api/{org}/v1/logs`, NOT `/api/{org}/otlp/v1/logs`. The latter
        // returns 404 from OpenObserve, and the log processor swallows
        // the export failure silently — which is why traces from this service
        // arrived for months while its logs never did. The Python worker has
        // always used this path; the two had simply drifted.
        url: `${endpoint}/api/${org}/v1/logs`,
        headers: apiKey ? { Authorization: `Basic ${apiKey}` } : {},
      }),
    ),
    traceExporter: new OTLPTraceExporter({
      url: `${endpoint}/api/${org}/v1/traces`,
      headers: apiKey ? { Authorization: `Basic ${apiKey}` } : {},
    }),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({
        url: `${endpoint}/api/${org}/v1/metrics`,
        headers: apiKey ? { Authorization: `Basic ${apiKey}` } : {},
      }),
      exportIntervalMillis: 30000,
    }),
    instrumentations: [
      // Kept for trace-context injection, but it is NOT what ships logs: it
      // bridges `pino`, and nothing under app/ imports pino. bridgeConsole()
      // below is what actually produces log records for this service.
      new PinoInstrumentation(),
      new HttpInstrumentation(),
      new ExpressInstrumentation(),
    ],
  });

  sdk.start();

  // Everything in this app logs with console.*, so without a bridge the OTLP
  // log pipeline has no input at all — an exporter wired to a source that never
  // emits. Rather than migrate every call site to pino, forward console here:
  // one place, and existing code keeps working unchanged.
  bridgeConsole();

  // Graceful shutdown
  process.on("SIGTERM", () => {
    sdk!
      .shutdown()
      .then(() => process.exit(0))
      .catch(() => process.exit(1));
  });

  return sdk;
}
