import "./openapi-extend.js";
import { OpenAPIRegistry, OpenApiGeneratorV3 } from "@asteasolutions/zod-to-openapi";
import { z } from "zod";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  UserSchema,
  WorkspaceSchema,
  SignInRequestSchema,
  SignInResponseSchema,
  SignUpRequestSchema,
  SignUpResponseSchema,
  RefreshTokenRequestSchema,
  RefreshTokenResponseSchema,
  SignOutRequestSchema,
  GetCurrentUserResponseSchema,
} from "./auth.schema.js";

import {
  JobSchema,
  JobConfigSchema,
  JobProgressSchema,
  JobProgressEventSchema,
  ListJobsRequestSchema,
  ListJobsResponseSchema,
  GetJobRequestSchema,
  GetJobResponseSchema,
  CreateJobRequestSchema,
  CreateJobResponseSchema,
  UpdateJobRequestSchema,
  UpdateJobResponseSchema,
  DeleteJobRequestSchema,
  PauseJobRequestSchema,
  ResumeJobRequestSchema,
  RetryJobRequestSchema,
} from "./job.schema.js";

import {
  PrincipalSchema,
  PaginationRequestSchema,
  PaginationResponseSchema,
  ErrorDetailSchema,
  JobStatusSchema,
  TimeRangeSchema,
  ResourceMetadataSchema,
} from "./common.schema.js";


const registry = new OpenAPIRegistry();

registry.register("User", UserSchema);
registry.register("Workspace", WorkspaceSchema);
registry.register("Job", JobSchema);
registry.register("JobConfig", JobConfigSchema);
registry.register("JobProgress", JobProgressSchema);
registry.register("JobProgressEvent", JobProgressEventSchema);
registry.register("Principal", PrincipalSchema);
registry.register("PaginationRequest", PaginationRequestSchema);
registry.register("PaginationResponse", PaginationResponseSchema);
registry.register("ErrorDetail", ErrorDetailSchema);
registry.register("JobStatus", JobStatusSchema);
registry.register("TimeRange", TimeRangeSchema);
registry.register("ResourceMetadata", ResourceMetadataSchema);

registry.registerPath({
  method: "post",
  path: "/api/v2/auth/login",
  summary: "Sign in",
  request: {
    body: {
      content: {
        "application/json": {
          schema: SignInRequestSchema,
        },
      },
    },
  },
  responses: {
    200: {
      description: "Successful sign in",
      content: {
        "application/json": {
          schema: SignInResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/auth/register",
  summary: "Sign up",
  request: {
    body: {
      content: {
        "application/json": {
          schema: SignUpRequestSchema,
        },
      },
    },
  },
  responses: {
    201: {
      description: "Successful sign up",
      content: {
        "application/json": {
          schema: SignUpResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/auth/refresh",
  summary: "Refresh access token",
  request: {
    body: {
      content: {
        "application/json": {
          schema: RefreshTokenRequestSchema,
        },
      },
    },
  },
  responses: {
    200: {
      description: "Token refreshed",
      content: {
        "application/json": {
          schema: RefreshTokenResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/auth/logout",
  summary: "Sign out",
  request: {
    body: {
      content: {
        "application/json": {
          schema: SignOutRequestSchema,
        },
      },
    },
  },
  responses: {
    204: {
      description: "Signed out successfully",
    },
  },
});

registry.registerPath({
  method: "get",
  path: "/api/v2/auth/me",
  summary: "Get current user",
  responses: {
    200: {
      description: "Current user",
      content: {
        "application/json": {
          schema: GetCurrentUserResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "get",
  path: "/api/v2/jobs",
  summary: "List jobs",
  request: {
    query: ListJobsRequestSchema.omit({ workspace_id: true }),
  },
  responses: {
    200: {
      description: "Jobs list",
      content: {
        "application/json": {
          schema: ListJobsResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "get",
  path: "/api/v2/jobs/{job_id}",
  summary: "Get job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
  },
  responses: {
    200: {
      description: "Job details",
      content: {
        "application/json": {
          schema: GetJobResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/jobs",
  summary: "Create job",
  request: {
    body: {
      content: {
        "application/json": {
          schema: CreateJobRequestSchema.omit({ workspace_id: true }),
        },
      },
    },
  },
  responses: {
    201: {
      description: "Job created",
      content: {
        "application/json": {
          schema: CreateJobResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "patch",
  path: "/api/v2/jobs/{job_id}",
  summary: "Update job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
    body: {
      content: {
        "application/json": {
          schema: UpdateJobRequestSchema.omit({ job_id: true }),
        },
      },
    },
  },
  responses: {
    200: {
      description: "Job updated",
      content: {
        "application/json": {
          schema: UpdateJobResponseSchema,
        },
      },
    },
  },
});

registry.registerPath({
  method: "delete",
  path: "/api/v2/jobs/{job_id}",
  summary: "Delete job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
  },
  responses: {
    204: {
      description: "Job deleted",
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/jobs/{job_id}/pause",
  summary: "Pause job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
  },
  responses: {
    204: {
      description: "Job paused",
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/jobs/{job_id}/resume",
  summary: "Resume job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
  },
  responses: {
    204: {
      description: "Job resumed",
    },
  },
});

registry.registerPath({
  method: "post",
  path: "/api/v2/jobs/{job_id}/retry",
  summary: "Retry job",
  request: {
    params: z.object({ job_id: z.string().uuid() }),
  },
  responses: {
    204: {
      description: "Job retried",
    },
  },
});

const generator = new OpenApiGeneratorV3(registry.definitions);

const document = generator.generateDocument({
  openapi: "3.1.0",
  info: {
    title: "Autoniix API",
    version: "2.0.0",
    description: "Autoniix API contracts (generated from Zod schemas)",
  },
  servers: [
    {
      url: "http://localhost:8080",
      description: "Local development",
    },
  ],
});

const outputPath = resolve(process.cwd(), "openapi.json");
writeFileSync(outputPath, JSON.stringify(document, null, 2));

console.log(`✅ OpenAPI spec generated: ${outputPath}`);
