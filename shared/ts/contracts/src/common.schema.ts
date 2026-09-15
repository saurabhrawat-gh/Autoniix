import { z } from "zod";

export const PrincipalSchema = z.object({
  user_id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  email: z.string().email(),
  roles: z.array(z.string()),
  global_roles: z.array(z.string()),
  permissions: z.array(z.string()),
});

export type Principal = z.infer<typeof PrincipalSchema>;

export const PaginationRequestSchema = z.object({
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().min(1).max(100).default(20),
  cursor: z.string().optional(),
});

export type PaginationRequest = z.infer<typeof PaginationRequestSchema>;

export const PaginationResponseSchema = z.object({
  total: z.number().int().min(0),
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
});

export type PaginationResponse = z.infer<typeof PaginationResponseSchema>;

export const ErrorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
  metadata: z.record(z.string()).optional(),
});

export type ErrorDetail = z.infer<typeof ErrorDetailSchema>;

export const JobStatusSchema = z.enum(["pending", "running", "completed", "failed", "paused", "stopped"]);

export type JobStatus = z.infer<typeof JobStatusSchema>;

export const TimeRangeSchema = z.object({
  start: z.string().datetime(),
  end: z.string().datetime(),
});

export type TimeRange = z.infer<typeof TimeRangeSchema>;

export const ResourceMetadataSchema = z.object({
  id: z.string().uuid(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  created_by: z.string().uuid(),
  updated_by: z.string().uuid(),
  version: z.number().int().min(0),
});

export type ResourceMetadata = z.infer<typeof ResourceMetadataSchema>;
