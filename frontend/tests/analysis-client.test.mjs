import { test } from "node:test";
import assert from "node:assert/strict";
import { setTimeout as wait } from "node:timers/promises";
import { AnalysisClient } from "../src/lib/analysis-client.ts";

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};
async function until(check) {
  for (let i = 0; i < 200; i++) {
    if (check()) return;
    await wait(2);
  }
  assert.fail("Expected state was not reached");
}
function setup(t, health = async () => ({}), options = {}) {
  const client = new AnalysisClient(health, {
    timeoutMs: 50,
    retryDelays: [],
    ...options,
  });
  t.after(() => client.stop());
  return client;
}
function resource(client, key = "calls", load = async () => ["live"]) {
  return client.resource({ key, demo: ["sample"], load });
}
function watch(t, handle) {
  const off = handle.subscribe(() => {});
  t.after(off);
}

test("demo content exists synchronously, before startup or any API response", async (t) => {
  const health = deferred();
  let loads = 0;
  const client = setup(t, () => health.promise);
  const r = resource(client, "calls", async () => {
    loads++;
    return ["live"];
  });
  watch(t, r);
  assert.deepEqual(r.getSnapshot().data, ["sample"]);
  assert.equal(r.getSnapshot().source, "demo");
  client.start();
  assert.equal(client.getConnection(), "connecting");
  assert.deepEqual(r.getSnapshot().data, ["sample"]);
  assert.equal(loads, 0);
  health.resolve({});
  await until(() => r.getSnapshot().source === "live");
  assert.deepEqual(r.getSnapshot().data, ["live"]);
  assert.equal(client.getConnection(), "live");
});
test("a hanging backend times out without clearing content or claiming live", async (t) => {
  const client = setup(t, () => new Promise(() => {}), { timeoutMs: 10 });
  const r = resource(client);
  watch(t, r);
  client.start();
  await until(() => client.getConnection() === "demo");
  assert.deepEqual(r.getSnapshot().data, ["sample"]);
  assert.equal(r.getSnapshot().source, "demo");
});
test("cold-start retries are bounded and recover automatically", async (t) => {
  let attempts = 0;
  const client = setup(
    t,
    async () => {
      if (++attempts < 3) throw Error("sleeping");
    },
    { retryDelays: [3, 5] },
  );
  const r = resource(client);
  watch(t, r);
  client.start();
  await until(() => r.getSnapshot().source === "live");
  assert.equal(attempts, 3);
  assert.equal(client.getConnection(), "live");
});
test("an unavailable backend stops retrying after its configured backoff", async (t) => {
  let attempts = 0;
  const client = setup(
    t,
    async () => {
      attempts++;
      throw Error("offline");
    },
    { retryDelays: [2, 3] },
  );
  const r = resource(client);
  watch(t, r);
  client.start();
  await until(() => attempts === 3);
  await wait(20);
  assert.equal(attempts, 3);
  assert.equal(client.getConnection(), "demo");
  assert.deepEqual(r.getSnapshot().data, ["sample"]);
});
test("a timed-out cold start stays connecting and recovers without manual retry", async (t) => {
  let attempts = 0;
  const states = [];
  const client = setup(t, () => {
    attempts++;
    return attempts === 1 ? new Promise(() => {}) : Promise.resolve({});
  }, { timeoutMs: 10, retryDelays: [5] });
  const off = client.subscribeConnection(() => states.push(client.getConnection()));
  t.after(off);
  const r = resource(client);
  watch(t, r);
  client.start();
  await until(() => r.getSnapshot().source === "live");
  assert.equal(attempts, 2);
  assert.deepEqual(states, ["live"]);
  assert.deepEqual(r.getSnapshot().data, ["live"]);
});
test("subscribers share one in-flight request and one cached response", async (t) => {
  let calls = 0;
  const client = setup(t);
  const definition = {
    key: "shared",
    demo: ["sample"],
    load: async () => {
      calls++;
      return ["live"];
    },
  };
  const a = client.resource(definition),
    b = client.resource(definition);
  assert.equal(a, b);
  watch(t, a);
  watch(t, b);
  client.start();
  await until(() => a.getSnapshot().source === "live");
  assert.equal(calls, 1);
});
test("partial API failures retain the relevant sample independently", async (t) => {
  const client = setup(t);
  const report = resource(client, "report", async () => ["real report"]);
  const claims = resource(client, "claims", async () => {
    throw Object.assign(Error("missing"), { status: 404 });
  });
  watch(t, report);
  watch(t, claims);
  client.start();
  await until(
    () => report.getSnapshot().source === "live" && claims.getSnapshot().error,
  );
  assert.deepEqual(claims.getSnapshot().data, ["sample"]);
  assert.equal(claims.getSnapshot().source, "demo");
  assert.equal(report.getSnapshot().source, "live");
});
test("successful endpoints do not wait for a hanging supporting request", async (t) => {
  const client = setup(t);
  const report = resource(client, "report");
  const transcript = resource(
    client,
    "transcript",
    () => new Promise(() => {}),
  );
  watch(t, report);
  watch(t, transcript);
  client.start();
  await until(() => report.getSnapshot().source === "live");
  assert.equal(transcript.getSnapshot().source, "demo");
  assert.deepEqual(transcript.getSnapshot().data, ["sample"]);
});
test("manual retry aborts a stale request and late completion cannot replace newer data", async (t) => {
  const old = deferred();
  let count = 0;
  let oldSignal;
  const client = setup(t);
  const r = resource(client, "report", (signal) => {
    if (++count === 1) {
      oldSignal = signal;
      return old.promise;
    }
    return Promise.resolve(["new"]);
  });
  watch(t, r);
  client.start();
  await until(() => count === 1);
  client.retry();
  await until(() => r.getSnapshot().source === "live");
  assert.equal(oldSignal.aborted, true);
  assert.deepEqual(r.getSnapshot().data, ["new"]);
  old.resolve(["stale"]);
  await wait(5);
  assert.deepEqual(r.getSnapshot().data, ["new"]);
});
test("late responses for another route remain in their own cache entry", async (t) => {
  const old = deferred();
  const client = setup(t);
  const a = resource(client, "AAPL", () => old.promise),
    b = resource(client, "MSFT", async () => ["Microsoft"]);
  watch(t, a);
  watch(t, b);
  client.start();
  await until(() => b.getSnapshot().source === "live");
  old.resolve(["Apple"]);
  await until(() => a.getSnapshot().source === "live");
  assert.deepEqual(b.getSnapshot().data, ["Microsoft"]);
});
test("a failed refresh keeps already loaded live data", async (t) => {
  let count = 0;
  const client = setup(t);
  const r = resource(client, "calls", async () => {
    if (++count > 1) throw Error("offline");
    return ["previously live"];
  });
  watch(t, r);
  client.start();
  await until(() => r.getSnapshot().source === "live");
  client.retry();
  await until(() => r.getSnapshot().error);
  assert.equal(r.getSnapshot().source, "live");
  assert.deepEqual(r.getSnapshot().data, ["previously live"]);
  assert.equal(client.getConnection(), "demo");
});
test("stopping cancels timers and requests; restarting works under StrictMode lifecycle", async (t) => {
  const first = deferred();
  let attempts = 0;
  const client = setup(t, async () => (++attempts === 1 ? first.promise : {}));
  const r = resource(client);
  watch(t, r);
  client.start();
  await until(() => attempts === 1);
  client.stop();
  client.start();
  await until(() => r.getSnapshot().source === "live");
  first.reject(Error("old request"));
  await wait(5);
  assert.equal(client.getConnection(), "live");
  assert.deepEqual(r.getSnapshot().data, ["live"]);
});
test("unknown calls remain identifiable and do not borrow another call’s data", async (t) => {
  const client = setup(t);
  const unknown = client.resource({
    key: "unknown",
    demo: null,
    load: async () => {
      throw Object.assign(Error("missing"), { status: 404 });
    },
  });
  watch(t, unknown);
  client.start();
  await until(() => unknown.getSnapshot().error);
  assert.equal(unknown.getSnapshot().source, "none");
  assert.equal(unknown.getSnapshot().data, null);
});
