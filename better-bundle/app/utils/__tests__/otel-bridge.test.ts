import { describe, it, expect, vi, beforeEach } from "vitest";

// Intercept the OTel logger the bridge emits into, so the real bridgeConsole()
// can run without an SDK, exporter or network.
const emitted: Array<Record<string, unknown>> = [];
vi.mock("@opentelemetry/api-logs", () => ({
  logs: { getLogger: () => ({ emit: (r: Record<string, unknown>) => emitted.push(r) }) },
}));

const { bridgeConsole } = await import("../otel-logger");

describe("console bridge", () => {
  beforeEach(() => {
    emitted.length = 0;
  });

  it("attributes a bridged console.error to the real call site", () => {
    bridgeConsole();
    console.error("checkout failed", { orderId: 1 });

    const rec = emitted.at(-1)!;
    const attrs = rec.attributes as Record<string, unknown>;

    expect(rec.severityText).toBe("ERROR");
    expect(String(rec.body)).toContain("checkout failed");
    // The point of the change: which module logged, not just which service.
    expect(String(attrs["code.filepath"])).toContain("otel-bridge.test.ts");
    expect(String(attrs["code.filepath"])).not.toContain("otel-logger");
    expect(attrs["code.lineno"]).toBeTypeOf("number");
  });

  it("keeps the original console output intact", () => {
    bridgeConsole();
    const spy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    console.log("still printed");
    spy.mockRestore();
    expect(String(emitted.at(-1)!.body)).toContain("still printed");
  });

  it("maps each console level to its OTel severity", () => {
    bridgeConsole();
    console.debug("d");
    console.warn("w");
    console.error("e");
    expect(emitted.map((r) => r.severityText)).toEqual(["DEBUG", "WARN", "ERROR"]);
  });
});
