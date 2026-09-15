import type { FastifyReply } from "fastify";

const ACCESS_MAX_AGE = 3600; // 1 hour
const REFRESH_MAX_AGE = 2592000; // 30 days

export function setAuthCookies(reply: FastifyReply, accessToken: string, refreshToken: string): void {
  reply
    .setCookie("access_token", accessToken, {
      path: "/",
      maxAge: ACCESS_MAX_AGE,
      httpOnly: true,
      secure: true,
      sameSite: "lax",
    })
    .setCookie("refresh_token", refreshToken, {
      path: "/",
      maxAge: REFRESH_MAX_AGE,
      httpOnly: true,
      secure: true,
      sameSite: "lax",
    })
    .setCookie("auth_status", "1", {
      path: "/",
      maxAge: REFRESH_MAX_AGE,
      httpOnly: false,
      secure: true,
      sameSite: "lax",
    });
}

export function clearAuthCookies(reply: FastifyReply): void {
  reply
    .clearCookie("access_token", { path: "/" })
    .clearCookie("refresh_token", { path: "/" })
    .clearCookie("auth_status", { path: "/" });
}
