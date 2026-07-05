'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import { authApi } from '@/lib/api-v2';
import { Button, Input, Card } from '@/lib/ui';
import { FormField } from '@/lib/components/FormField';

const requestSchema = z.object({ email: z.string().email('Invalid email') });
const resetSchema = z.object({
  token: z.string().min(1, 'Token is required'),
  password: z.string().min(8, 'At least 8 characters'),
});
type RequestValues = z.infer<typeof requestSchema>;
type ResetValues = z.infer<typeof resetSchema>;

export default function ForgotPasswordPage() {
  const [stage, setStage] = useState<'request' | 'reset' | 'slack' | 'done'>('request');
  const [serverError, setServerError] = useState('');

  const reqForm = useForm<RequestValues>({ resolver: zodResolver(requestSchema) });
  const resetForm = useForm<ResetValues>({ resolver: zodResolver(resetSchema), defaultValues: { token: '' } });

  async function handleRequest(values: RequestValues) {
    setServerError('');
    try {
      const res = await authApi.forgot(values.email);
      if (res.reset_token) {
        resetForm.setValue('token', res.reset_token);
        setStage('reset');
      } else {
        setStage('slack');
      }
    } catch (err: any) {
      setServerError(err.message || 'Request failed');
    }
  }

  async function handleReset(values: ResetValues) {
    setServerError('');
    try {
      await authApi.reset(values.token, values.password);
      setStage('done');
    } catch (err: any) {
      setServerError(err.message || 'Reset failed');
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-full max-w-md px-6">
        <Card variant="elevated" padding="xl" className="space-y-6">
          <div className="text-center space-y-1">
            <h1 className="text-xl font-semibold text-content-primary">Reset password</h1>
            <p className="text-content-tertiary text-sm">
              {stage === 'request' && 'Enter your email to receive a reset link.'}
              {stage === 'slack' && "If an account exists for that email, we've sent you a reset link. Check your inbox (and spam folder)."}
              {stage === 'reset' && 'Enter the reset token and your new password.'}
              {stage === 'done' && 'Password updated successfully.'}
            </p>
          </div>

          {serverError && (
            <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
          )}

          {stage === 'request' && (
            <form onSubmit={reqForm.handleSubmit(handleRequest)} className="space-y-4">
              <FormField id="fp-email" label="Email" required error={reqForm.formState.errors.email}>
                <Input id="fp-email" type="email" placeholder="you@example.com" autoFocus {...reqForm.register('email')} />
              </FormField>
              <Button type="submit" size="lg" className="w-full" loading={reqForm.formState.isSubmitting}>
                {reqForm.formState.isSubmitting ? 'Sending…' : 'Send reset link'}
              </Button>
            </form>
          )}

          {stage === 'reset' && (
            <form onSubmit={resetForm.handleSubmit(handleReset)} className="space-y-4">
              <FormField id="fp-token" label="Reset token" required error={resetForm.formState.errors.token}>
                <Input id="fp-token" type="text" placeholder="Paste token from email" className="font-mono" {...resetForm.register('token')} />
              </FormField>
              <FormField id="fp-pw" label="New password" required error={resetForm.formState.errors.password}>
                <Input id="fp-pw" type="password" placeholder="At least 8 characters" {...resetForm.register('password')} />
              </FormField>
              <Button type="submit" size="lg" className="w-full" loading={resetForm.formState.isSubmitting}>
                {resetForm.formState.isSubmitting ? 'Updating…' : 'Set new password'}
              </Button>
            </form>
          )}

          {stage === 'slack' && (
            <Button asChild size="lg" className="w-full">
              <Link href="/login">Back to login</Link>
            </Button>
          )}

          {stage === 'done' && (
            <Button asChild size="lg" className="w-full">
              <Link href="/login">Back to login</Link>
            </Button>
          )}

          <p className="text-center text-xs text-content-tertiary">
            <Link href="/login" className="text-accent hover:underline">← Back to login</Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
