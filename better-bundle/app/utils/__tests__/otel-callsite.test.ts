import { describe, it, expect } from "vitest";
import { callSite } from "../otel-logger";

/**
 * Without these attributes every log line from this service arrives under
 * `instrumentation_library_name: "console"` — you can tell it came from
 * remix-app, but not which route wrote it, which is the first thing you want
 * from an error.
 *
 * Each test calls through a wrapper because that is how production uses it:
 * the boundary is the `bridged` console function, which is always on the
 * stack at the moment of capture.
 */

// Stands in for the bridged console.* wrapper.
function bridgeLike(): Record<string, string | number> {
  return callSite(bridgeLike);
}

describe("callSite", () => {
  it("names the file and line of the caller, not the bridge", () => {
    const attrs = bridgeLike();
    expect(attrs["code.filepath"]).toContain("otel-callsite.test.ts");
    expect(attrs["code.lineno"]).toBeTypeOf("number");
    expect(attrs["code.lineno"]).toBeGreaterThan(0);
  });

  it("uses the same attribute names the Python worker emits", () => {
    // Shared columns in OpenObserve, or the two services cannot be queried
    // the same way.
    const attrs = bridgeLike();
    expect(Object.keys(attrs).every((k) => k.startsWith("code."))).toBe(true);
    expect(attrs).toHaveProperty("code.filepath");
    expect(attrs).toHaveProperty("code.lineno");
  });

  it("reports different lines for different call sites", () => {
    const a = bridgeLike();
    const b = bridgeLike();
    expect(a["code.lineno"]).not.toBe(b["code.lineno"]);
  });

  it("excludes the bridge's own frame", () => {
    const attrs = bridgeLike();
    expect(String(attrs["code.filepath"])).not.toContain("otel-logger");
  });

  it("restores Error.stackTraceLimit so it never leaks globally", () => {
    const before = Error.stackTraceLimit;
    bridgeLike();
    expect(Error.stackTraceLimit).toBe(before);
  });

  it("returns {} rather than throwing when no stack can be produced", () => {
    // V8 yields an EMPTY stack when the boundary is not on the call stack.
    // Documented here because the failure is silent: no attributes, no error.
    // Production always passes the live `bridged` function, so this is the
    // misuse case, not the normal one.
    expect(callSite(() => {})).toEqual({});
  });

  it("survives a runtime that cannot capture stacks at all", () => {
    const original = Error.captureStackTrace;
    try {
      // @ts-expect-error - simulating a non-V8 runtime
      Error.captureStackTrace = undefined;
      expect(() => bridgeLike()).not.toThrow();
    } finally {
      Error.captureStackTrace = original;
    }
  });
});
