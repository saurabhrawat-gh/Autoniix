import { z } from "zod";
import { PrincipalSchema } from "./common.schema.js";

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string().min(1).max(255),
  avatar_url: z.string().url().nullable(),
  roles: z.array(z.string()),
  created_at: z.string().datetime(),
});

export type User = z.infer<typeof UserSchema>;

export const WorkspaceSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(255),
  owner_id: z.string().uuid(),
  created_at: z.string().datetime(),
});

export type Workspace = z.infer<typeof WorkspaceSchema>;

export const SignInRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(255),
  workspace_id: z.string().uuid().optional(),
});

export type SignInRequest = z.infer<typeof SignInRequestSchema>;

export const SignInResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  expires_at: z.string().datetime(),
  user: UserSchema,
});

export type SignInResponse = z.infer<typeof SignInResponseSchema>;

export const SignUpRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(255),
  full_name: z.string().min(1).max(255),
  workspace_name: z.string().min(1).max(255),
});

export type SignUpRequest = z.infer<typeof SignUpRequestSchema>;

export const SignUpResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  expires_at: z.string().datetime(),
  user: UserSchema,
  workspace: WorkspaceSchema,
});

export type SignUpResponse = z.infer<typeof SignUpResponseSchema>;

export const RefreshTokenRequestSchema = z.object({
  refresh_token: z.string(),
});

export type RefreshTokenRequest = z.infer<typeof RefreshTokenRequestSchema>;

export const RefreshTokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  expires_at: z.string().datetime(),
});

export type RefreshTokenResponse = z.infer<typeof RefreshTokenResponseSchema>;

export const SignOutRequestSchema = z.object({
  refresh_token: z.string().optional(),
});

export type SignOutRequest = z.infer<typeof SignOutRequestSchema>;

export const VerifyTokenRequestSchema = z.object({
  token: z.string(),
});

export type VerifyTokenRequest = z.infer<typeof VerifyTokenRequestSchema>;

export const VerifyTokenResponseSchema = z.object({
  valid: z.boolean(),
  principal: PrincipalSchema,
});

export type VerifyTokenResponse = z.infer<typeof VerifyTokenResponseSchema>;

export const GetCurrentUserResponseSchema = z.object({
  user: UserSchema,
  workspace: WorkspaceSchema,
});

export type GetCurrentUserResponse = z.infer<
  typeof GetCurrentUserResponseSchema
>;
