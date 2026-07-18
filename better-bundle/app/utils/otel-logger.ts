import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
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
        url: `${endpoint}/api/${org}/otlp/v1/logs`,
        headers: apiKey ? { Authorization: `Basic ${apiKey}` } : {},
      }),
    ),
    instrumentations: [
      new PinoInstrumentation(),
      new HttpInstrumentation(),
      new ExpressInstrumentation(),
    ],
  });

  sdk.start();

  // Graceful shutdown
  process.on("SIGTERM", () => {
    sdk!
      .shutdown()
      .then(() => process.exit(0))
      .catch(() => process.exit(1));
  });

  return sdk;
}
