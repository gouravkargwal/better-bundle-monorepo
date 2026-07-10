/**
 * OpenTelemetry instrumentation for BetterBundle Remix App.
 *
 * Sets up trace AND log export to OpenObserve via OTLP.
 * This MUST be imported before any other module to ensure spans
 * are created for all HTTP requests and Kafka messages.
 *
 * Usage in entry.server.tsx:
 *   import "./instrumentation";
 */

import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { Resource } from "@opentelemetry/resources";
import { SEMRESATTRS_SERVICE_NAME } from "@opentelemetry/semantic-conventions";

// KafkaJS instrumentation for trace propagation across Kafka messages
import { KafkajsInstrumentation } from "@opentelemetry/instrumentation-kafkajs";

// OTel Logging SDK
import { LoggerProvider } from "@opentelemetry/sdk-logs";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { BatchLogRecordProcessor } from "@opentelemetry/sdk-logs";
import { logs } from "@opentelemetry/api-logs";

// Pino instrumentation to capture Remix/node logging through OTel
// The Remix app uses pino for structured logging, not winston
import { PinoInstrumentor } from "@opentelemetry/instrumentation-pino";

const serviceName = process.env.OTEL_SERVICE_NAME || "remix-app";
const otlpEndpoint =
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://openobserve:5080";
const openObserveOrgId = process.env.OPENOBSERVE_ORG_ID || "default";

// Build OTLP headers with Basic Auth if credentials are available
const otlpHeaders: Record<string, string> = {};
const openObserveEmail = process.env.OPENOBSERVE_EMAIL;
const openObservePassword = process.env.OPENOBSERVE_PASSWORD;
if (openObserveEmail && openObservePassword) {
  const encoded = Buffer.from(
    `${openObserveEmail}:${openObservePassword}`
  ).toString("base64");
  otlpHeaders["Authorization"] = `Basic ${encoded}`;
}

const resource = new Resource({
  [SEMRESATTRS_SERVICE_NAME]: serviceName,
  "service.namespace": "betterbundle",
});

// Only initialize if endpoint is reachable (don't crash if OTel isn't available)
try {
  // ═══════════════════════════════════════════
  //  LOGGING — LoggerProvider + OTLP exporter
  // ═══════════════════════════════════════════
  const loggerProvider = new LoggerProvider({ resource });

  const otlpLogExporter = new OTLPLogExporter({
    url: `${otlpEndpoint.replace(/\/+$/, "")}/api/${openObserveOrgId}/v1/logs`,
    headers: otlpHeaders,
  });

  loggerProvider.addLogRecordProcessor(
    new BatchLogRecordProcessor(otlpLogExporter)
  );

  logs.setGlobalLoggerProvider(loggerProvider);

  // ═══════════════════════════════════════════
  //  TRACING — NodeSDK with OTLP exporter
  // ═══════════════════════════════════════════
  const sdk = new NodeSDK({
    resource,
    traceExporter: new OTLPTraceExporter({
      url: `${otlpEndpoint.replace(/\/+$/, "")}/api/${openObserveOrgId}/v1/traces`,
      headers: otlpHeaders,
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        "@opentelemetry/instrumentation-http": { enabled: true },
        "@opentelemetry/instrumentation-express": { enabled: true },
        "@opentelemetry/instrumentation-fs": { enabled: false },
        "@opentelemetry/instrumentation-net": { enabled: false },
        "@opentelemetry/instrumentation-dns": { enabled: false },
      }),
      // KafkaJS instrumentation for trace context propagation across Kafka
      new KafkajsInstrumentation({
        consumerHook: (span, topic, partition, _message) => {
          span.setAttribute("messaging.kafka.topic", topic);
          span.setAttribute("messaging.kafka.partition", partition);
        },
        producerHook: (span, topic, messages) => {
          span.setAttribute("messaging.kafka.topic", topic);
          span.setAttribute("messaging.kafka.message_count", messages.length);
        },
      }),
      // Pino instrumentation captures Remix logs via OTel
      new PinoInstrumentor({
        enabled: true,
      }),
    ],
  });

  // Start the SDK
  sdk.start();

  // Graceful shutdown
  const shutdown = () => {
    sdk
      .shutdown()
      .then(() => loggerProvider.shutdown())
      .then(() => console.log("OpenTelemetry SDK shut down"))
      .catch((err) => console.error("Error shutting down OpenTelemetry", err));
  };

  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
} catch (err) {
  console.warn(
    "OpenTelemetry initialization failed, continuing without tracing:",
    err
  );
}

export {};
