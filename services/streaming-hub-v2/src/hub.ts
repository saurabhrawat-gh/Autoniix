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
  subscribe(
    opts: SubscribeOptions,
    push: (event: Event) => void,
    close: () => void
  ): string {
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
}
