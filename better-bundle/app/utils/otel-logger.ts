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
import { SimpleLogRecordProcessor } from "@opentelemetry/sdk-logs";
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

let consoleBridged = false;

/**
 * Forward console.* to the OpenTelemetry log pipeline, keeping the original
 * console behaviour intact so local terminal output is unchanged.
 *
 * Emitting inside the active span's context is what lets a log line be clicked
 * through from its trace: OpenObserve correlates on trace_id/span_id, and a log
 * record created outside a span carries neither.
 */
function bridgeConsole(): void {
  if (consoleBridged) return;
  consoleBridged = true;
  const otelLogger = logs.getLogger("console");

  for (const [method, severityNumber, severityText] of CONSOLE_LEVELS) {
    const original = (console[method] as (...a: unknown[]) => void).bind(console);
    (console as unknown as Record<string, unknown>)[method] = (...args: unknown[]) => {
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
          context: context.active(),
        });
      } catch {
        // A logger that throws while logging takes the request with it. The
        // original console call above has already run, so the line is not lost.
      }
    };
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
    logRecordProcessor: new SimpleLogRecordProcessor(
      new OTLPLogExporter({
        // `/api/{org}/v1/logs`, NOT `/api/{org}/otlp/v1/logs`. The latter
        // returns 404 from OpenObserve, and SimpleLogRecordProcessor swallows
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
