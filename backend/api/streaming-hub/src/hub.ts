import Redis from "ioredis";
import { randomUUID } from "node:crypto";
import type { FastifyBaseLogger } from "fastify";

/**
 * Wire format for events on the shared Redis channel.
 * Matches the shape used by the legacy Go streaming-hub so both can
 * co-exist during the migration.
 */
export interface Event {
  id: string;
  type: string;
  workspace_id: string;
  ts: number;
  data?: Record<string, unknown>;
  /**
   * Redis Streams monotonic ID (e.g. "1710000000000-0"). Set when the
   * event was resumed/read from a Redis stream so clients can send this
   * back as `Last-Event-ID` to resume without gaps. Missing on legacy
   * pub/sub events (they were never durable).
   */
  stream_id?: string;
}

export interface SubscribeOptions {
  workspaceId: string;
  eventTypes?: string[];
}

interface Subscriber {
  id: string;
  workspaceId: string;
  eventTypes: Set<string>;
  push: (event: Event) => void;
  close: () => void;
}

const REDIS_CHANNEL = "autoniix:events";

/**
 * In-process pub/sub hub backed by Redis for multi-instance fan-out.
 *
 * Producers call `publish()` — the event is pushed to Redis and immediately
 * fanned out to local subscribers. A separate Redis subscription pipeline
 * receives events published by other instances and fans them out here too.
 */
export class Hub {
  private subscribers = new Map<string, Subscriber>();
  private publisher: Redis;
  private subscriber: Redis;
  private log: FastifyBaseLogger;
  private closed = false;

  constructor(redisUrl: string, log: FastifyBaseLogger) {
    this.log = log;
    // Two connections: one for publishing, one for subscribing (ioredis requirement)
    this.publisher = new Redis(redisUrl, { lazyConnect: true });
    this.subscriber = new Redis(redisUrl, { lazyConnect: true });
  }

  async start(): Promise<void> {
    await Promise.all([this.publisher.connect(), this.subscriber.connect()]);
    await this.subscriber.subscribe(REDIS_CHANNEL);
    this.subscriber.on("message", (channel, payload) => {
      if (channel !== REDIS_CHANNEL) return;
      try {
        const event = JSON.parse(payload) as Event;
        this.fanout(event);
      } catch (err) {
        this.log.warn({ err }, "streaming.redis_parse_failed");
      }
    });
    this.log.info({ channel: REDIS_CHANNEL }, "streaming.hub_started");
  }

  async stop(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    for (const sub of this.subscribers.values()) sub.close();
    this.subscribers.clear();
    await this.subscriber.quit().catch(() => undefined);
    await this.publisher.quit().catch(() => undefined);
    this.log.info("streaming.hub_stopped");
  }

  /**
   * Register a subscriber. Returns the subscriber id (opaque) so callers can
   * unsubscribe later. `push` is invoked once per matching event.
   */
  subscribe(opts: SubscribeOptions, push: (event: Event) => void, close: () => void): string {
    const id = randomUUID();
    this.subscribers.set(id, {
      id,
      workspaceId: opts.workspaceId,
      eventTypes: new Set(opts.eventTypes ?? []),
      push,
      close,
    });
    return id;
  }

  unsubscribe(id: string): void {
    const sub = this.subscribers.get(id);
    if (!sub) return;
    this.subscribers.delete(id);
    try {
      sub.close();
    } catch {
      // ignore
    }
  }

  /**
   * Publish an event: fans out locally, then broadcasts to Redis so other
   * instances of streaming-hub-v2 (and the legacy Go hub during migration)
   * can also fan out to their subscribers.
   */
  async publish(input: Omit<Event, "id" | "ts"> & Partial<Pick<Event, "id" | "ts">>): Promise<Event> {
    const event: Event = {
      id: input.id ?? randomUUID(),
      type: input.type,
      workspace_id: input.workspace_id,
      ts: input.ts ?? Date.now(),
      data: input.data,
    };
    // Fan out locally first (immediate feedback for same-instance subs)
    this.fanout(event);
    // Then to Redis for cross-instance fan-out
    try {
      await this.publisher.publish(REDIS_CHANNEL, JSON.stringify(event));
    } catch (err) {
      this.log.warn({ err, event_id: event.id }, "streaming.redis_publish_failed");
    }
    return event;
  }

  private fanout(event: Event): void {
    for (const sub of this.subscribers.values()) {
      if (sub.workspaceId && sub.workspaceId !== event.workspace_id) continue;
      if (sub.eventTypes.size > 0 && !sub.eventTypes.has(event.type)) continue;
      try {
        sub.push(event);
      } catch (err) {
        this.log.warn({ err, subscriber_id: sub.id }, "streaming.push_failed");
      }
    }
  }

  get subscriberCount(): number {
    return this.subscribers.size;
  }

  /**
   * Replay events from a per-content-id Redis stream since ``lastId``.
   *
   * The Python side writes job progress events to ``stream:jobs:{content_id}``
   * (see `backend/workers/temporal/workers/activities/common.py`). Clients
   * that reconnect an SSE stream with a ``Last-Event-ID`` header (or the
   * WS equivalent) can call this to backfill missed events before switching
   * to live fan-out via pub/sub subscribe.
   *
   * ``lastId`` should be the Redis stream id (e.g. "1710000000000-0"), or
   * "$" for "only new events" (the default XREAD behavior). We use "0" to
   * mean "everything currently retained" when the caller passes no header.
   */
  async replaySince(contentId: string, lastId: string, limit = 200): Promise<Event[]> {
    if (!contentId) return [];
    const key = `stream:jobs:${contentId}`;
    const startId = lastId && lastId !== "$" ? lastId : "0";
    try {
      // XRANGE returns entries with id > startId when we bump the last char.
      // Simpler: use XREAD COUNT limit STREAMS key startId (returns events > startId).
      const raw = (await this.publisher.xread("COUNT", limit, "STREAMS", key, startId)) as
        [string, [string, string[]][]][] | null;
      const first = raw?.[0];
      if (!first) return [];
      const [, entries] = first;
      const out: Event[] = [];
      for (const [streamId, fields] of entries) {
        const obj: Record<string, string> = {};
        for (let i = 0; i + 1 < fields.length; i += 2) {
          const k = fields[i];
          const v = fields[i + 1];
          if (k !== undefined && v !== undefined) obj[k] = v;
        }
        let detail: Record<string, unknown> = {};
        try {
          detail = obj.detail ? (JSON.parse(obj.detail) as Record<string, unknown>) : {};
        } catch {
          detail = { raw: obj.detail ?? "" };
        }
        out.push({
          id: obj.event_id ?? streamId,
          type: `job.${obj.phase ?? "unknown"}.${obj.status ?? "unknown"}`,
          workspace_id: obj.channel_id ?? "",
          ts: Number(streamId.split("-")[0]) || Date.now(),
          data: {
            content_id: obj.content_id ?? contentId,
            channel_id: obj.channel_id ?? "",
            phase: obj.phase ?? "",
            status: obj.status ?? "",
            cost_usd: Number(obj.cost_usd ?? 0),
            ...detail,
          },
          stream_id: streamId,
        });
      }
      return out;
    } catch (err) {
      this.log.warn({ err, key }, "streaming.replay_failed");
      return [];
    }
  }
}
