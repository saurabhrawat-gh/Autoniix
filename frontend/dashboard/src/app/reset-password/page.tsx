"use client";

import { useState, Suspense } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { authApi } from "@/lib/api-v2";
import { Button, Input, Card } from "@/lib/ui";
import { FormField } from "@/lib/components/FormField";
import { resetPasswordSchema, type ResetPasswordValues } from "@/lib/schemas/auth";

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [stage, setStage] = useState<"form" | "done">("form");
  const [serverError, setServerError] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
  });

  async function onSubmit(values: ResetPasswordValues) {
    setServerError("");
    try {
      await authApi.reset(token, values.password);
      setStage("done");
    } catch (err: any) {
      setServerError(err.message || "Reset failed — the link may have expired");
    }
  }

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <p className="text-status-error text-sm">Missing reset token. Request a new link.</p>
        <Link href="/forgot-password" className="text-accent hover:underline text-sm">
          Request new link
        </Link>
      </div>
    );
  }

  return (
    <Card variant="elevated" padding="xl" className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="text-xl font-semibold text-content-primary">Set new password</h1>
        <p className="text-content-tertiary text-sm">
          {stage === "form" ? "Choose a strong password for your account." : "Password updated successfully."}
        </p>
      </div>

      {serverError && (
        <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
      )}

      {stage === "form" && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField id="rp-pw" label="New password" required error={errors.password}>
            <Input id="rp-pw" type="password" placeholder="At least 8 characters" autoFocus {...register("password")} />
          </FormField>
          <FormField id="rp-confirm" label="Confirm password" required error={errors.confirm}>
            <Input id="rp-confirm" type="password" placeholder="Repeat your new password" {...register("confirm")} />
          </FormField>
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>
            {isSubmitting ? "Updating…" : "Set new password"}
          </Button>
        </form>
      )}

      {stage === "done" && (
        <Button asChild size="lg" className="w-full">
          <Link href="/login">Back to login</Link>
        </Button>
      )}

      <p className="text-center text-xs text-content-tertiary">
        <Link href="/login" className="text-accent hover:underline">
          ← Back to login
        </Link>
      </p>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-full max-w-md px-6">
        <Suspense
          fallback={
            <div className="flex justify-center">
              <span className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
            </div>
          }
        >
          <ResetPasswordContent />
        </Suspense>
      </div>
    </div>
  );
}
