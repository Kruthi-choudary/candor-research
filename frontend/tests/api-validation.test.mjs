import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { api } from "../src/lib/api.ts";
import {
  isCalls,
  isReport,
  isClaims,
  isTranscript,
  isEvaluation,
} from "../src/lib/api-validation.ts";
import { AnalysisClient } from "../src/lib/analysis-client.ts";
import { setTimeout as wait } from "node:timers/promises";
const demo = JSON.parse(
  readFileSync(new URL("../src/data/demo.json", import.meta.url), "utf8"),
);

test("bundled samples preserve existing API shapes and stay lightweight", () => {
  assert.equal(demo.calls.length, 4);
  assert.ok(isCalls({ calls: demo.calls }));
  assert.ok(isEvaluation(demo.evaluation));
  for (const key of Object.keys(demo.reports)) {
    assert.ok(isReport(demo.reports[key]), key);
    assert.ok(isClaims(demo.claims[key]), key);
    assert.ok(isTranscript(demo.transcripts[key]), key);
    assert.ok(demo.transcripts[key].segments.length < 50);
  }
  assert.ok(Buffer.byteLength(JSON.stringify(demo)) < 80000);
});
test("malformed shapes and impossible benchmark values are rejected", () => {
  assert.equal(isCalls({ calls: [{ ticker: "AAPL" }] }), false);
  assert.equal(isTranscript({ segments: [] }), false);
  assert.equal(isReport({}), false);
  const evaluation = structuredClone(demo.evaluation);
  evaluation.claim_coverage.avg_f1 = 9;
  assert.equal(isEvaluation(evaluation), false);
  const report = structuredClone(Object.values(demo.reports)[0]);
  report.audio_features_summary.mean_pitch_hz = "loud";
  assert.equal(isReport(report), false);
});
test("a malformed 200 response cannot replace the demo cache", async (t) => {
  const original = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = original;
  });
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ calls: "bad payload" }),
  });
  const client = new AnalysisClient(async () => ({}), {
    timeoutMs: 50,
    retryDelays: [],
  });
  t.after(() => client.stop());
  const r = client.resource({
    key: "calls",
    demo: { calls: demo.calls },
    load: api.listCalls,
  });
  const off = r.subscribe(() => {});
  t.after(off);
  client.start();
  for (let i = 0; i < 100 && !r.getSnapshot().error; i++) await wait(2);
  assert.ok(r.getSnapshot().error);
  assert.equal(r.getSnapshot().source, "demo");
  assert.equal(r.getSnapshot().data.calls.length, 4);
});
test("health response bodies are validated before connection becomes live", async (t) => {
  const original = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = original;
  });
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ companies: "bad payload" }),
  });
  const client = new AnalysisClient((signal) => api.listCompanies(signal), {
    timeoutMs: 50,
    retryDelays: [],
  });
  t.after(() => client.stop());
  client.start();
  for (let i = 0; i < 100 && client.getConnection() === "connecting"; i++)
    await wait(2);
  assert.equal(client.getConnection(), "demo");
});
test("a valid report for the wrong call is rejected", async (t) => {
  const original = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = original;
  });
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => demo.reports["MSFT/Q1-2025"],
  });
  await assert.rejects(api.getCall("AAPL", "Q1-2025"), /different call/);
});
