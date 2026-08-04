import { describe, it, expect, vi } from "vitest";
import type { FastifyBaseLogger } from "fastify";
import { Hub, type Event } from "../src/hub.js";

/**
 * Unit tests for the in-process fan-out logic. Redis is stubbed by using
 * a URL that will fail — `start()` isn't called, so the pub/sub side is
 * never exercised, only local subscribe/publish/fanout paths.
 */

function fakeLog(): FastifyBaseLogger {
  const noop = vi.fn();
  const log: any = {
    info: noop,
    warn: noop,
    error: noop,
    debug: noop,
    trace: noop,
    fatal: noop,
    child: () => log,
    level: "silent",
  };
  return log as FastifyBaseLogger;
}

function makeHub(): Hub {
  // Real ioredis will try to connect, but we never call start() so it stays lazy
  return new Hub("redis://127.0.0.1:1", fakeLog());
}

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: "ev-1",
    type: "job.progress",
    workspace_id: "ws-1",
    ts: 1000,
    data: {},
    ...overrides,
  };
}

describe("Hub", () => {
  it("workspace filter — matching workspace receives event", () => {
    const hub = makeHub();
    const received: Event[] = [];
    hub.subscribe(
      { workspaceId: "ws-1" },
      (e) => received.push(e),
      () => undefined
    );
    (hub as any).fanout(makeEvent({ workspace_id: "ws-1" }));
    expect(received).toHaveLength(1);
  });

  it("workspace filter — mismatched workspace is ignored", () => {
    const hub = makeHub();
    const received: Event[] = [];
    hub.subscribe(
      { workspaceId: "ws-1" },
      (e) => received.push(e),
      () => undefined
    );
    (hub as any).fanout(makeEvent({ workspace_id: "ws-2" }));
    expect(received).toHaveLength(0);
  });

  it("event type filter — matching type is delivered", () => {
    const hub = makeHub();
    const received: Event[] = [];
    hub.subscribe(
      { workspaceId: "ws-1", eventTypes: ["job.progress"] },
      (e) => received.push(e),
      () => undefined
    );
    (hub as any).fanout(makeEvent({ type: "job.progress" }));
    expect(received).toHaveLength(1);
  });

  it("event type filter — non-matching type is ignored", () => {
    const hub = makeHub();
    const received: Event[] = [];
    hub.subscribe(
      { workspaceId: "ws-1", eventTypes: ["job.progress"] },
      (e) => received.push(e),
      () => undefined
    );
    (hub as any).fanout(makeEvent({ type: "job.completed" }));
    expect(received).toHaveLength(0);
  });

  it("unsubscribe removes subscriber and calls close hook", () => {
    const hub = makeHub();
    const received: Event[] = [];
    const closeSpy = vi.fn();
    const id = hub.subscribe(
      { workspaceId: "ws-1" },
      (e) => received.push(e),
      closeSpy
    );
    expect(hub.subscriberCount).toBe(1);
    hub.unsubscribe(id);
    expect(hub.subscriberCount).toBe(0);
    expect(closeSpy).toHaveBeenCalledOnce();
    (hub as any).fanout(makeEvent({ workspace_id: "ws-1" }));
    expect(received).toHaveLength(0);
  });

  it("push handler that throws does not break fanout for other subscribers", () => {
    const hub = makeHub();
    hub.subscribe(
      { workspaceId: "ws-1" },
      () => {
        throw new Error("boom");
      },
      () => undefined
    );
    const received: Event[] = [];
    hub.subscribe(
      { workspaceId: "ws-1" },
      (e) => received.push(e),
      () => undefined
    );
    (hub as any).fanout(makeEvent({ workspace_id: "ws-1" }));
    expect(received).toHaveLength(1);
  });
});
