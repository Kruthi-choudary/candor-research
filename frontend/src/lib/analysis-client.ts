/** Shared demo-first cache. No React or browser globals: lifecycle and races are testable. */
export type DataSource = "demo" | "live" | "none";
export type ConnectionState = "connecting" | "live" | "demo";
export interface ResourceSnapshot<T> {
  data: T | null;
  source: DataSource;
  refreshing: boolean;
  error: string | null;
}
export interface ResourceDefinition<T> {
  key: string;
  demo: T | null;
  load: (signal: AbortSignal) => Promise<T>;
}
export interface ResourceHandle<T> {
  getSnapshot: () => ResourceSnapshot<T>;
  subscribe: (listener: () => void) => () => void;
}
interface Entry<T> {
  definition: ResourceDefinition<T>;
  snapshot: ResourceSnapshot<T>;
  listeners: Set<() => void>;
  attempts: number;
  revision: number;
  pending: AbortController | null;
  timer: ReturnType<typeof setTimeout> | null;
  terminal: boolean;
  needsRefresh: boolean;
  handle?: ResourceHandle<T>;
}
interface Options {
  timeoutMs?: number;
  retryDelays?: number[];
}

export class AnalysisClient {
  private entries = new Map<string, Entry<unknown>>();
  private listeners = new Set<() => void>();
  private state: ConnectionState = "connecting";
  private running = false;
  private healthAttempts = 0;
  private healthRevision = 0;
  private healthRequest: AbortController | null = null;
  private healthTimer: ReturnType<typeof setTimeout> | null = null;
  private health: (signal: AbortSignal) => Promise<unknown>;
  private timeoutMs: number;
  private retryDelays: number[];

  constructor(
    health: (signal: AbortSignal) => Promise<unknown>,
    options: Options = {},
  ) {
    this.health = health;
    this.timeoutMs = options.timeoutMs ?? 12000;
    this.retryDelays = options.retryDelays ?? [2000, 4000, 8000, 16000, 30000];
  }
  getConnection = () => this.state;
  subscribeConnection = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private setConnection(state: ConnectionState) {
    if (state === this.state) return;
    this.state = state;
    this.listeners.forEach((listener) => listener());
  }
  start() {
    if (this.running) return;
    this.running = true;
    this.healthAttempts = 0;
    this.setConnection("connecting");
    void this.probe();
  }
  stop() {
    this.running = false;
    this.healthRevision++;
    this.healthRequest?.abort();
    this.healthRequest = null;
    if (this.healthTimer) clearTimeout(this.healthTimer);
    this.healthTimer = null;
    for (const entry of this.entries.values()) {
      entry.revision++;
      entry.pending?.abort();
      entry.pending = null;
      if (entry.timer) clearTimeout(entry.timer);
      entry.timer = null;
      this.update(entry, { refreshing: false });
    }
  }
  /** A manual retry supersedes old requests but retains all displayed content. */
  retry = () => {
    if (!this.running) return;
    this.healthRevision++;
    this.healthRequest?.abort();
    this.healthRequest = null;
    if (this.healthTimer) clearTimeout(this.healthTimer);
    this.healthTimer = null;
    this.healthAttempts = 0;
    for (const entry of this.entries.values()) {
      entry.revision++;
      entry.pending?.abort();
      entry.pending = null;
      if (entry.timer) clearTimeout(entry.timer);
      entry.timer = null;
      entry.attempts = 0;
      entry.terminal = false;
      entry.needsRefresh = true;
      this.update(entry, { refreshing: false });
    }
    this.setConnection("connecting");
    void this.probe();
  };
  resource<T>(definition: ResourceDefinition<T>): ResourceHandle<T> {
    let entry = this.entries.get(definition.key) as Entry<T> | undefined;
    if (!entry) {
      entry = {
        definition,
        snapshot: {
          data: definition.demo,
          source: definition.demo === null ? "none" : "demo",
          refreshing: false,
          error: null,
        },
        listeners: new Set(),
        attempts: 0,
        revision: 0,
        pending: null,
        timer: null,
        terminal: false,
        needsRefresh: true,
      };
      const current = entry;
      entry.handle = {
        getSnapshot: () => current.snapshot,
        subscribe: (listener) => {
          current.listeners.add(listener);
          if (this.running && this.state === "live") void this.refresh(current);
          return () => {
            current.listeners.delete(listener);
            if (!current.listeners.size && current.timer) {
              clearTimeout(current.timer);
              current.timer = null;
            }
          };
        },
      };
      this.entries.set(definition.key, entry as Entry<unknown>);
    }
    return entry.handle!;
  }
  private update<T>(entry: Entry<T>, changes: Partial<ResourceSnapshot<T>>) {
    entry.snapshot = { ...entry.snapshot, ...changes };
    entry.listeners.forEach((listener) => listener());
  }
  private async request<T>(
    load: (signal: AbortSignal) => Promise<T>,
    controller: AbortController,
  ): Promise<T> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let abort: () => void = () => {};
    try {
      return await Promise.race([
        Promise.resolve().then(() => load(controller.signal)),
        new Promise<never>((_, reject) => {
          abort = () => reject(new Error("Request cancelled."));
          controller.signal.addEventListener("abort", abort, { once: true });
          timer = setTimeout(() => {
            reject(new Error("The live service did not respond in time."));
            controller.abort();
          }, this.timeoutMs);
        }),
      ]);
    } finally {
      if (timer) clearTimeout(timer);
      controller.signal.removeEventListener("abort", abort);
    }
  }
  private async probe() {
    if (!this.running || this.healthRequest) return;
    const revision = ++this.healthRevision;
    const controller = new AbortController();
    this.healthRequest = controller;
    this.healthAttempts++;
    try {
      await this.request(this.health, controller);
      if (!this.running || revision !== this.healthRevision) return;
      this.setConnection("live");
      for (const entry of this.entries.values())
        if (entry.listeners.size) void this.refresh(entry);
    } catch {
      if (!this.running || revision !== this.healthRevision) return;
      this.setConnection("demo");
      const delay = this.retryDelays[this.healthAttempts - 1];
      if (delay !== undefined)
        this.healthTimer = setTimeout(() => {
          this.healthTimer = null;
          void this.probe();
        }, delay);
    } finally {
      if (revision === this.healthRevision) this.healthRequest = null;
    }
  }
  private async refresh<T>(entry: Entry<T>) {
    if (
      !this.running ||
      this.state !== "live" ||
      entry.pending ||
      entry.timer ||
      entry.terminal ||
      !entry.needsRefresh ||
      entry.attempts > this.retryDelays.length
    )
      return;
    const revision = ++entry.revision;
    const controller = new AbortController();
    entry.pending = controller;
    entry.attempts++;
    this.update(entry, { refreshing: true });
    try {
      const data = await this.request(entry.definition.load, controller);
      if (!this.running || revision !== entry.revision) return;
      entry.needsRefresh = false;
      this.update(entry, {
        data,
        source: "live",
        refreshing: false,
        error: null,
      });
    } catch (error) {
      if (!this.running || revision !== entry.revision) return;
      const status =
        typeof error === "object" && error !== null && "status" in error
          ? error.status
          : null;
      entry.terminal =
        typeof status === "number" &&
        status >= 400 &&
        status < 500 &&
        status !== 429;
      this.update(entry, {
        refreshing: false,
        error:
          "Live content is unavailable. Showing the available preview or previously loaded data.",
      });
      const delay = this.retryDelays[entry.attempts - 1];
      if (!entry.terminal && delay !== undefined && entry.listeners.size) {
        entry.timer = setTimeout(() => {
          entry.timer = null;
          void this.refresh(entry);
        }, delay);
      }
      // Recheck availability after network/server failures; don't flood a sleeping backend.
      if (
        !entry.terminal &&
        (status === null || (typeof status === "number" && status >= 500)) &&
        !this.healthRequest &&
        !this.healthTimer &&
        this.state === "live"
      ) {
        this.setConnection("demo");
        this.healthAttempts = 0;
        const recoveryDelay = this.retryDelays[0];
        if (recoveryDelay !== undefined)
          this.healthTimer = setTimeout(() => {
            this.healthTimer = null;
            void this.probe();
          }, recoveryDelay);
      }
    } finally {
      if (revision === entry.revision) entry.pending = null;
    }
  }
}
