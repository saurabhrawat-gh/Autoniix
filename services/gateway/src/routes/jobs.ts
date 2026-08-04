import type { FastifyInstance } from "fastify";
import {
  ListJobsRequestSchema,
  GetJobRequestSchema,
  CreateJobRequestSchema,
  UpdateJobRequestSchema,
  DeleteJobRequestSchema,
  PauseJobRequestSchema,
  ResumeJobRequestSchema,
  RetryJobRequestSchema,
  type ListJobsRequest,
  type CreateJobRequest,
  type UpdateJobRequest,
} from "@autoniix/contracts";
import { JobRepository } from "../repositories/job.repository.js";

export async function jobRoutes(app: FastifyInstance): Promise<void> {
  const jobRepo = new JobRepository(app.db);

  app.get("/api/v2/jobs", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const query = request.query as any;
      const page = parseInt(query.page || "1", 10);
      const pageSize = Math.min(parseInt(query.page_size || "20", 10), 100);
      const statusFilter = query.status_filter
        ? Array.isArray(query.status_filter)
          ? query.status_filter
          : [query.status_filter]
        : undefined;
      const sortBy = query.sort_by || "created_at";
      const sortDesc = query.sort_desc !== "false";

      const { jobs, total } = await jobRepo.findByWorkspace(
        request.principal.workspace_id,
        {
          statusFilter,
          sortBy,
          sortDesc,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        }
      );

      return reply.send({
        jobs: jobs.map((j) => jobRepo.toJob(j)),
        pagination: {
          total,
          page,
          page_size: pageSize,
          next_cursor: null,
          has_more: total > page * pageSize,
        },
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch jobs",
      });
    }
  });

  app.get("/api/v2/jobs/:job_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };

      const job = await jobRepo.findById(job_id);
      if (!job) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (job.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      return reply.send({
        job: jobRepo.toJob(job),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to fetch job",
      });
    }
  });

  app.post("/api/v2/jobs", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const body = CreateJobRequestSchema.parse(request.body) as CreateJobRequest;
      const { channel_id, config } = body;

      const job = await jobRepo.create(
        request.principal.workspace_id,
        channel_id,
        config
      );

      return reply.code(201).send({
        job: jobRepo.toJob(job),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(400).send({
        error: "Bad Request",
        message: error.message,
      });
    }
  });

  app.patch("/api/v2/jobs/:job_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };
      const body = UpdateJobRequestSchema.parse({
        ...(request.body as any),
        job_id,
      }) as UpdateJobRequest;

      const existingJob = await jobRepo.findById(job_id);
      if (!existingJob) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (existingJob.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      const job = await jobRepo.update(job_id, body.config);

      return reply.send({
        job: jobRepo.toJob(job),
      });
    } catch (error: any) {
      request.log.error(error);
      return reply.code(400).send({
        error: "Bad Request",
        message: error.message,
      });
    }
  });

  app.delete("/api/v2/jobs/:job_id", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };

      const job = await jobRepo.findById(job_id);
      if (!job) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (job.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      await jobRepo.delete(job_id);

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to delete job",
      });
    }
  });

  app.post("/api/v2/jobs/:job_id/pause", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };

      const job = await jobRepo.findById(job_id);
      if (!job) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (job.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      await jobRepo.updateStatus(job_id, "paused");

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to pause job",
      });
    }
  });

  app.post("/api/v2/jobs/:job_id/resume", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };

      const job = await jobRepo.findById(job_id);
      if (!job) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (job.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      await jobRepo.updateStatus(job_id, "running");

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to resume job",
      });
    }
  });

  app.post("/api/v2/jobs/:job_id/retry", async (request, reply) => {
    if (!request.principal) {
      return reply.code(401).send({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    try {
      const { job_id } = request.params as { job_id: string };

      const job = await jobRepo.findById(job_id);
      if (!job) {
        return reply.code(404).send({
          error: "Not Found",
          message: "Job not found",
        });
      }

      if (job.workspace_id !== request.principal.workspace_id) {
        return reply.code(403).send({
          error: "Forbidden",
          message: "Access denied to this job",
        });
      }

      await jobRepo.updateStatus(job_id, "pending");

      return reply.code(204).send();
    } catch (error: any) {
      request.log.error(error);
      return reply.code(500).send({
        error: "Internal Server Error",
        message: "Failed to retry job",
      });
    }
  });
}
