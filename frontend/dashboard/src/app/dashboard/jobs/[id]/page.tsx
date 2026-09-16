"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { jobsApi, dashboardApi } from "@/lib/api-v2";
import { isLoggedIn, wsProgress } from "@/lib/api-v2";
import { cn, statusColor, PHASE_LABELS, PHASE_ORDER } from "@/lib/utils";
import { StatusIcon } from "@/lib/components/StatusIcon";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/lib/toast";
import { PageHeader } from "@/lib/components/PageHeader";
import { SkeletonCard } from "@/lib/components/Skeleton";
import { Button } from "@/lib/ui";

export default function JobDetailPage() {
  const router = useRouter();
  const params = useParams();
  const contentId = params.id as string;
  const [progress, setProgress] = useState<any>(null);
  const [output, setOutput] = useState<any>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"progress" | "output" | "metadata">("progress");
  const [copied, setCopied] = useState("");
  const [reviewAction, setReviewAction] = useState<"none" | "approving" | "rejecting" | "approved" | "rejected">(
    "none"
  );
  const wsRef = useRef<WebSocket | null>(null);
  const [systemStopped, setSystemStopped] = useState(false);
  const [retryBusy, setRetryBusy] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);
  const { showToast } = useToast();

  const loadAll = useCallback(async () => {
    const [p, o, m] = await Promise.all([
      jobsApi.progress(contentId).catch(() => null),
      jobsApi.output(contentId).catch(() => null),
      jobsApi.metadata(contentId).catch(() => null),
    ]);
    if (p) setProgress(p.data);
    if (o) {
      setOutput(o.data);
      if (o.data?.status === "rejected") setReviewAction("rejected");
    }
    if (m) setMetadata(m.data);
  }, [contentId]);

  const connectWs = useCallback(() => {
    try {
      const ws = wsProgress(contentId);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "event") {
          setProgress((prev: any) => {
            if (!prev) return prev;
            return { ...prev, timeline: [...(prev.timeline || []), msg] };
          });
        }
        if (msg.type === "done") loadAll();
      };
    } catch {}
  }, [contentId, loadAll]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    loadAll();
    connectWs();
    dashboardApi
      .stats()
      .then((res) => setSystemStopped(res.data?.emergency_stop === true))
      .catch(() => {});
    return () => {
      wsRef.current?.close();
    };
  }, [router, contentId, loadAll, connectWs]);

  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  }

  async function handleApprove() {
    setReviewAction("approving");
    try {
      await jobsApi.approve(contentId);
      setReviewAction("approved");
      showToast("Video approved", "success");
    } catch (e: any) {
      showToast(e?.message || "Approve failed", "error");
      setReviewAction("none");
    }
  }

  async function handleReject() {
    setReviewAction("rejecting");
    try {
      await jobsApi.reject(contentId);
      setReviewAction("rejected");
      showToast("Video rejected", "info");
    } catch (e: any) {
      showToast(e?.message || "Reject failed", "error");
      setReviewAction("none");
    }
  }

  if (!progress)
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader
          title={contentId}
          subtitle="Loading job details…"
          crumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Progress", href: "/dashboard/progress" },
            { label: contentId },
          ]}
        />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </main>
      </div>
    );

  const isDelivered = progress.current_status === "delivered";
  const isFailed = progress.current_status === "failed";
  const isStopped = progress.current_status === "stopped";
  const showReviewPanel = isDelivered && reviewAction !== "approved" && reviewAction !== "rejected";
  const isApproved = reviewAction === "approved";
  const isRejected = reviewAction === "rejected";

  async function handleRetry() {
    if (retryBusy) return;
    setRetryBusy(true);
    try {
      const res = await jobsApi.retry(contentId);
      showToast("New video started", "success");
      const newId = (res as any)?.data?.new_content_id;
      if (newId) {
        router.push(`/dashboard/jobs/${newId}`);
      } else {
        loadAll();
      }
    } catch (e: any) {
      showToast(e?.message || "Retry failed", "error");
    } finally {
      setRetryBusy(false);
    }
  }

  async function handleRestart() {
    if (restartBusy) return;
    setRestartBusy(true);
    try {
      const res = await jobsApi.restart(contentId);
      showToast(
        `Restarting from ${PHASE_LABELS[(res as any)?.data?.resume_from] || (res as any)?.data?.resume_from || "checkpoint"}`,
        "success"
      );
      loadAll();
    } catch (e: any) {
      showToast(e?.message || "Restart failed", "error");
    } finally {
      setRestartBusy(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title={contentId}
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Progress", href: "/dashboard/progress" },
          { label: contentId },
        ]}
        fallbackHref="/dashboard/progress"
        subtitle={
          <div className="flex items-center gap-2">
            <span
              className={cn("inline-flex items-center gap-1 text-xs font-medium", statusColor(progress.current_status))}
            >
              <StatusIcon status={progress.current_status} size={12} colored={false} />
              {PHASE_LABELS[progress.current_status] || progress.current_status}
            </span>
            {progress.total_cost > 0 && (
              <span className="text-xs text-content-tertiary">· ${progress.total_cost.toFixed(2)}</span>
            )}
            {isApproved && <span className="badge bg-status-success/10 text-status-success">✓ Approved</span>}
            {isRejected && <span className="badge bg-status-error/10 text-status-error">✕ Rejected</span>}
          </div>
        }
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {/* Lockdown banner */}
          {systemStopped && (
            <div className="mb-6 p-4 rounded-lg bg-status-error/10 border border-status-error/20">
              <div className="flex items-center gap-3">
                <span className="text-status-error text-lg">■</span>
                <div>
                  <h3 className="text-sm font-semibold text-status-error">System Stopped</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">All controls are frozen.</p>
                </div>
              </div>
            </div>
          )}
          {/* Stepper — always visible */}
          <div className={cn("card p-5 mb-6", systemStopped && "lockdown-frost")}>
            <div className="flex items-center gap-1">
              {PHASE_ORDER.map((phase, idx) => {
                const events = (progress.timeline || []).filter((e: any) => e.phase === phase);
                const completed = events.some((e: any) => e.status === "completed");
                const started = events.some((e: any) => e.status === "started");
                const failed = events.some((e: any) => e.status === "failed");
                const isActive = started && !completed && !failed;
                return (
                  <div key={phase} className="flex-1 flex flex-col items-center gap-1.5">
                    <div className="flex items-center w-full">
                      {idx > 0 && (
                        <div className={cn("flex-1 h-0.5", completed ? "bg-status-success" : "bg-surface-3")} />
                      )}
                      <div
                        className={cn(
                          "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0 transition-all",
                          failed
                            ? "bg-status-error text-white"
                            : completed
                              ? "bg-status-success text-white"
                              : isActive
                                ? "bg-accent text-white ring-4 ring-accent/20 animate-pulse"
                                : "bg-surface-3 text-content-tertiary"
                        )}
                      >
                        {failed ? "✕" : completed ? "✓" : idx + 1}
                      </div>
                      {idx < PHASE_ORDER.length - 1 && (
                        <div className={cn("flex-1 h-0.5", completed ? "bg-status-success" : "bg-surface-3")} />
                      )}
                    </div>
                    <span
                      className={cn(
                        "text-[10px] font-medium text-center leading-tight",
                        isActive
                          ? "text-accent"
                          : completed
                            ? "text-status-success"
                            : failed
                              ? "text-status-error"
                              : "text-content-tertiary"
                      )}
                    >
                      {PHASE_LABELS[phase]}
                    </span>
                  </div>
                );
              })}
            </div>
            {/* Live status */}
            {progress.live && (
              <div className="mt-4 pt-4 border-t border-border flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                <span className="text-sm text-content-primary font-medium">
                  {PHASE_LABELS[progress.live.phase] || progress.live.phase}
                </span>
                <span className="text-xs text-content-tertiary">${progress.live.accrued_cost?.toFixed(2)} spent</span>
                {progress.live.paused && <span className="badge bg-status-warning/10 text-status-warning">Paused</span>}
              </div>
            )}
          </div>

          {/* Stopped Panel — shown when job has been stopped by user */}
          {isStopped && (
            <div className="card p-5 mb-6 border-2 border-status-warning/30 bg-status-warning/5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-status-warning">Job Stopped</h3>
                  <p className="text-xs text-content-tertiary mt-1">
                    This job was stopped by user. You can resume from the last checkpoint or start fresh.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {progress.checkpoint && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRestart}
                      disabled={restartBusy}
                      className="text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10"
                    >
                      {restartBusy
                        ? "Restarting..."
                        : `Restart from ${PHASE_LABELS[progress.checkpoint] || progress.checkpoint}`}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleRetry}
                    disabled={retryBusy}
                    className="text-accent bg-accent/5 border-accent/15 hover:bg-accent/10"
                  >
                    {retryBusy ? "Retrying..." : "Retry (Fresh)"}
                  </Button>
                </div>
              </div>
              {progress.error_message && (
                <div className="px-3 py-2 rounded bg-status-warning/10 text-xs text-status-warning font-mono">
                  {progress.error_message}
                </div>
              )}
            </div>
          )}

          {/* Failed Panel — shown when job has failed */}
          {isFailed && (
            <div className="card p-5 mb-6 border-2 border-status-error/30 bg-status-error/5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-status-error">Job Failed</h3>
                  <p className="text-xs text-content-tertiary mt-1">
                    This job failed during production. You can review the error, adjust channel settings if needed, and
                    retry.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/dashboard/channels/${progress.channel_id}`}
                    className="px-4 py-2 border rounded-lg text-xs font-medium text-content-primary bg-surface-0 border-border hover:bg-surface-1 transition-all"
                  >
                    Channel Settings
                  </Link>
                  {progress.checkpoint && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRestart}
                      disabled={restartBusy}
                      className="text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10"
                    >
                      {restartBusy
                        ? "Restarting..."
                        : `Restart from ${PHASE_LABELS[progress.checkpoint] || progress.checkpoint}`}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleRetry}
                    disabled={retryBusy}
                    className="text-accent bg-accent/5 border-accent/15 hover:bg-accent/10"
                  >
                    {retryBusy ? "Retrying..." : "Retry (Fresh)"}
                  </Button>
                </div>
              </div>
              {progress.error_message && (
                <div className="px-3 py-2 rounded bg-status-error/10 text-xs text-status-error font-mono">
                  {progress.error_message}
                </div>
              )}
            </div>
          )}

          {/* Review Panel — shown when video is delivered and not yet reviewed */}
          {showReviewPanel && (
            <div className="card p-5 mb-6 border-2 border-status-warning/30">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-content-primary">Review Required</h3>
                  <p className="text-xs text-content-tertiary mt-1">
                    Video has been delivered. Please review the output and mark as complete or reject for regeneration.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleReject}
                    disabled={reviewAction === "rejecting"}
                    className="text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10"
                  >
                    {reviewAction === "rejecting" ? "Rejecting…" : "Reject & Regenerate"}
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleApprove}
                    disabled={reviewAction === "approving"}
                    loading={reviewAction === "approving"}
                  >
                    {reviewAction === "approving" ? "Approving…" : "✓ Mark as Complete"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Approved / Rejected confirmation */}
          {isApproved && (
            <div className="card p-4 mb-6 bg-status-success/5 border-status-success/20">
              <div className="flex items-center gap-2 text-sm text-status-success font-medium">
                <span>✓</span> Video approved and marked as complete.
              </div>
            </div>
          )}
          {isRejected && (
            <div className="card p-4 mb-6 bg-status-error/5 border-status-error/20">
              <div className="flex items-center gap-2 text-sm text-status-error font-medium">
                <span>✕</span> Video rejected. You can trigger a new video from the dashboard.
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="card overflow-hidden">
            <div className="flex border-b border-border px-5" role="tablist" aria-label="Job sections">
              {(["progress", "output", "metadata"] as const).map((t) => (
                <Button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === t}
                  variant="ghost"
                  onClick={() => setActiveTab(t)}
                  className={cn(
                    "h-auto px-4 py-3 text-sm font-medium capitalize relative rounded-t",
                    activeTab === t
                      ? "text-accent hover:text-accent"
                      : "text-content-tertiary hover:text-content-primary"
                  )}
                >
                  {t === "progress" ? "Event Log" : t}
                  {activeTab === t && (
                    <motion.span
                      layoutId="job-tab-underline"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full"
                      transition={{ type: "spring", stiffness: 500, damping: 35 }}
                    />
                  )}
                </Button>
              ))}
            </div>

            <div className="p-6">
              <AnimatePresence mode="wait">
                {/* Progress Timeline */}
                {activeTab === "progress" && (
                  <motion.div
                    key="tab-progress"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                  >
                    {(progress.timeline || []).length === 0 ? (
                      <div className="text-center py-12 text-content-tertiary text-sm">
                        No events yet. Trigger a video to see real-time progress here.
                      </div>
                    ) : (
                      <div className="space-y-0">
                        {(progress.timeline || []).map((ev: any, i: number) => (
                          <div
                            key={i}
                            className="flex items-start gap-3 py-2.5 border-b border-border/50 last:border-0"
                          >
                            <span className={cn("mt-0.5 inline-flex", statusColor(ev.status))}>
                              <StatusIcon status={ev.status} size={14} colored={false} />
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-content-primary">
                                  {PHASE_LABELS[ev.phase] || ev.phase}
                                </span>
                                <span className={cn("badge text-[10px]", statusColor(ev.status), "bg-current/5")}>
                                  {ev.status}
                                </span>
                                {ev.cost_usd > 0 && (
                                  <span className="text-xs text-content-tertiary">${ev.cost_usd.toFixed(3)}</span>
                                )}
                              </div>
                              {ev.detail && Object.keys(ev.detail).length > 0 && (
                                <div className="text-xs text-content-tertiary mt-1 truncate max-w-[500px]">
                                  {Object.entries(ev.detail)
                                    .map(([k, v]) => {
                                      const val =
                                        typeof v === "string" && v.length > 60 ? v.slice(0, 60) + "…" : String(v);
                                      return `${k}: ${val}`;
                                    })
                                    .join(" · ")}
                                </div>
                              )}
                            </div>
                            <span className="text-xs text-content-tertiary whitespace-nowrap">
                              {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}

                {/* Output */}
                {activeTab === "output" && (
                  <motion.div
                    key="tab-output"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="space-y-6"
                  >
                    {output?.video_url ? (
                      <div>
                        <video src={output.video_url} controls className="w-full rounded-lg max-h-[400px] bg-black" />
                        <div className="mt-4 flex flex-wrap gap-2">
                          <Button asChild size="sm">
                            <a href={output.download_url} download>
                              ⬇ Download Video
                            </a>
                          </Button>
                          {output.youtube_url && (
                            <Button asChild variant="secondary" size="sm">
                              <a href={output.youtube_url} target="_blank" rel="noreferrer">
                                View on YouTube ↗
                              </a>
                            </Button>
                          )}
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={async () => {
                              try {
                                await jobsApi.restart(contentId);
                                showToast("Re-rendering video...", "success");
                                loadAll();
                              } catch {
                                showToast("Recreate failed", "error");
                              }
                            }}
                          >
                            ↻ Recreate Video
                          </Button>
                        </div>
                        {output.total_cost > 0 && (
                          <div className="mt-2 text-xs text-content-tertiary">
                            Total cost: ${output.total_cost.toFixed(4)}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-12">
                        <div className="text-content-tertiary text-sm mb-3">
                          {progress?.current_phase === "rendering"
                            ? "Rendering in progress..."
                            : "Video not yet rendered."}
                        </div>
                        {progress?.current_phase === "rendering" && (
                          <div className="w-32 mx-auto h-1.5 bg-surface-2 rounded-full overflow-hidden">
                            <div className="h-full bg-accent rounded-full animate-pulse w-2/3" />
                          </div>
                        )}
                      </div>
                    )}

                    {output?.thumbnails && output.thumbnails.length > 0 && (
                      <div>
                        <h3 className="text-xs font-semibold text-content-secondary mb-3">Thumbnails</h3>
                        <div className="flex gap-3 flex-wrap">
                          {output.thumbnails.map((url: string, i: number) => (
                            <Image
                              key={i}
                              src={url}
                              alt={`Thumbnail ${i + 1}`}
                              width={160}
                              height={90}
                              unoptimized
                              className="h-24 w-auto rounded-lg border border-border hover:shadow-elevated transition-shadow"
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}

                {/* Metadata */}
                {activeTab === "metadata" && (
                  <motion.div
                    key="tab-metadata"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="space-y-3"
                  >
                    {metadata ? (
                      <>
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-xs font-semibold text-content-secondary">YouTube Metadata</h3>
                          <div className="flex items-center gap-3">
                            <Button
                              type="button"
                              variant="link"
                              size="sm"
                              onClick={() => {
                                const all = [
                                  metadata.title,
                                  "",
                                  metadata.description || "",
                                  "",
                                  (metadata.tags || []).join(", "),
                                  "",
                                  (metadata.hashtags || []).join(" "),
                                ].join("\n");
                                copyToClipboard(all, "All");
                              }}
                              className="h-auto p-0 text-[11px] text-accent hover:text-accent/80"
                            >
                              {copied === "All" ? "✓ Copied All" : "Copy All"}
                            </Button>
                            <span className="text-[11px] text-content-tertiary">Click any field to copy</span>
                          </div>
                        </div>
                        <MetaField label="Title" value={metadata.title} onCopy={copyToClipboard} copied={copied} />
                        <MetaField
                          label="Description"
                          value={metadata.description}
                          onCopy={copyToClipboard}
                          copied={copied}
                          multiline
                        />
                        <MetaField
                          label="Tags"
                          value={(metadata.tags || []).join(", ")}
                          onCopy={copyToClipboard}
                          copied={copied}
                        />
                        <MetaField
                          label="Hashtags"
                          value={(metadata.hashtags || []).join(" ")}
                          onCopy={copyToClipboard}
                          copied={copied}
                        />
                        <MetaField
                          label="Category"
                          value={metadata.category}
                          onCopy={copyToClipboard}
                          copied={copied}
                        />
                        <MetaField
                          label="Privacy Status"
                          value={metadata.privacy_status}
                          onCopy={copyToClipboard}
                          copied={copied}
                        />
                        <MetaField
                          label="Content Mode"
                          value={metadata.content_mode}
                          onCopy={copyToClipboard}
                          copied={copied}
                        />
                        {metadata.seo_score != null && (
                          <div className="flex items-center gap-4 text-xs text-content-secondary pt-3 border-t border-border">
                            <span>
                              SEO Score:{" "}
                              <span className="font-semibold text-content-primary">{metadata.seo_score}</span>/10
                            </span>
                            {metadata.content_mode && (
                              <span className="badge bg-accent/10 text-accent text-[10px]">
                                {metadata.content_mode}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-center py-12 text-content-tertiary text-sm">Metadata not yet generated.</div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function MetaField({
  label,
  value,
  onCopy,
  copied,
  multiline,
}: {
  label: string;
  value: string;
  onCopy: (text: string, label: string) => void;
  copied: string;
  multiline?: boolean;
}) {
  if (!value) return null;
  return (
    <div
      onClick={() => onCopy(value, label)}
      className="cursor-pointer group bg-surface-1 rounded-lg p-4 hover:bg-surface-2 transition-all border border-transparent hover:border-border"
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] font-medium text-content-tertiary uppercase tracking-wider">{label}</span>
        <span className="text-[11px] text-content-tertiary group-hover:text-accent transition-colors font-medium">
          {copied === label ? "✓ Copied" : "Copy"}
        </span>
      </div>
      {multiline ? (
        <pre className="text-sm text-content-primary whitespace-pre-wrap font-sans leading-relaxed">{value}</pre>
      ) : (
        <div className="text-sm text-content-primary">{value}</div>
      )}
    </div>
  );
}
