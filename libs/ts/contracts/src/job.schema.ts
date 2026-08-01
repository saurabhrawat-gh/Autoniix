import { z } from "zod";
import { JobStatusSchema, PaginationRequestSchema, PaginationResponseSchema, TimeRangeSchema } from "./common.schema.js";

export const JobConfigSchema = z.object({
  num_videos: z.number().int().min(1).max(100),
  niche: z.string().min(1).max(255),
  auto_publish: z.boolean().default(false),
  parameters: z.record(z.string()).optional(),
});

export type JobConfig = z.infer<typeof JobConfigSchema>;

export const JobProgressSchema = z.object({
  total_videos: z.number().int().min(0),
  completed_videos: z.number().int().min(0),
  failed_videos: z.number().int().min(0),
  current_stage: z.string(),
  progress_percent: z.number().min(0).max(100),
  started_at: z.string().datetime().nullable(),
  estimated_completion: z.string().datetime().nullable(),
});

export type JobProgress = z.infer<typeof JobProgressSchema>;

export const JobSchema = z.object({
  id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  channel_id: z.string().uuid(),
  status: JobStatusSchema,
  config: JobConfigSchema,
  progress: JobProgressSchema.nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  completed_at: z.string().datetime().nullable(),
  error_message: z.string().nullable(),
});

export type Job = z.infer<typeof JobSchema>;

export const ListJobsRequestSchema = z.object({
  workspace_id: z.string().uuid(),
  pagination: PaginationRequestSchema.optional(),
  status_filter: z.array(JobStatusSchema).optional(),
  time_range: TimeRangeSchema.optional(),
  sort_by: z.string().optional(),
  sort_desc: z.boolean().default(false),
});

export type ListJobsRequest = z.infer<typeof ListJobsRequestSchema>;

export const ListJobsResponseSchema = z.object({
  jobs: z.array(JobSchema),
  pagination: PaginationResponseSchema,
});

export type ListJobsResponse = z.infer<typeof ListJobsResponseSchema>;

export const GetJobRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type GetJobRequest = z.infer<typeof GetJobRequestSchema>;

export const GetJobResponseSchema = z.object({
  job: JobSchema,
});

export type GetJobResponse = z.infer<typeof GetJobResponseSchema>;

export const CreateJobRequestSchema = z.object({
  workspace_id: z.string().uuid(),
  channel_id: z.string().uuid(),
  config: JobConfigSchema,
});

export type CreateJobRequest = z.infer<typeof CreateJobRequestSchema>;

export const CreateJobResponseSchema = z.object({
  job: JobSchema,
});

export type CreateJobResponse = z.infer<typeof CreateJobResponseSchema>;

export const UpdateJobRequestSchema = z.object({
  job_id: z.string().uuid(),
  config: JobConfigSchema,
});

export type UpdateJobRequest = z.infer<typeof UpdateJobRequestSchema>;

export const UpdateJobResponseSchema = z.object({
  job: JobSchema,
});

export type UpdateJobResponse = z.infer<typeof UpdateJobResponseSchema>;

export const DeleteJobRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type DeleteJobRequest = z.infer<typeof DeleteJobRequestSchema>;

export const PauseJobRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type PauseJobRequest = z.infer<typeof PauseJobRequestSchema>;

export const ResumeJobRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type ResumeJobRequest = z.infer<typeof ResumeJobRequestSchema>;

export const RetryJobRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type RetryJobRequest = z.infer<typeof RetryJobRequestSchema>;

export const StreamJobProgressRequestSchema = z.object({
  job_id: z.string().uuid(),
});

export type StreamJobProgressRequest = z.infer<
  typeof StreamJobProgressRequestSchema
>;

export const JobProgressEventSchema = z.object({
  job_id: z.string().uuid(),
  status: JobStatusSchema,
  progress: JobProgressSchema.nullable(),
  stage: z.string(),
  message: z.string(),
  timestamp: z.string().datetime(),
});

export type JobProgressEvent = z.infer<typeof JobProgressEventSchema>;
