import { UserSchema, JobSchema } from "./index.js";

const testUser = {
  id: "550e8400-e29b-41d4-a716-446655440000",
  email: "test@example.com",
  full_name: "Test User",
  avatar_url: null,
  roles: ["admin"],
  created_at: new Date().toISOString(),
};

const testJob = {
  id: "660e8400-e29b-41d4-a716-446655440000",
  workspace_id: "770e8400-e29b-41d4-a716-446655440000",
  channel_id: "880e8400-e29b-41d4-a716-446655440000",
  status: "pending" as const,
  config: {
    num_videos: 5,
    niche: "tech",
    auto_publish: true,
  },
  progress: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  completed_at: null,
  error_message: null,
};

console.log("Testing Zod schema validation...\n");

try {
  const validatedUser = UserSchema.parse(testUser);
  console.log("✅ User schema validation passed");
  console.log(JSON.stringify(validatedUser, null, 2));
} catch (error) {
  console.error("❌ User schema validation failed:", error);
  process.exit(1);
}

try {
  const validatedJob = JobSchema.parse(testJob);
  console.log("\n✅ Job schema validation passed");
  console.log(JSON.stringify(validatedJob, null, 2));
} catch (error) {
  console.error("❌ Job schema validation failed:", error);
  process.exit(1);
}

console.log("\n✅ All schema validations passed!");
