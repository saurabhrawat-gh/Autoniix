'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api-v2';
import { ThemeToggle } from '@/lib/theme';
import { Button, Input, Card } from '@/lib/ui';
import { FormField } from '@/lib/components/FormField';

const schema = z.object({
  workspaceName: z.string().min(2, 'At least 2 characters').max(60),
  email: z.string().email('Invalid email address'),
  name: z.string().optional(),
  password: z.string().min(8, 'At least 8 characters'),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(values: Values) {
    setServerError(null);
    try {
      await authApi.register(values.email, values.password, values.workspaceName, values.name || undefined);
      await authApi.login(values.email, values.password);
      router.push('/onboarding');
    } catch (e: any) {
      setServerError(e?.message || 'Registration failed');
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen relative">
      <div className="absolute top-5 right-5"><ThemeToggle /></div>

      <div className="w-full max-w-md px-6">
        <Card variant="elevated" padding="xl">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="text-center space-y-1">
              <h1 className="text-xl font-semibold text-content-primary">Create your workspace</h1>
              <p className="text-content-tertiary text-xs">
                You&apos;ll be the owner. Invite teammates after setup.
              </p>
            </div>

            {serverError && (
              <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
            )}

            <FormField id="r-ws" label="Workspace name" required error={errors.workspaceName}>
              <Input id="r-ws" placeholder="Acme Studios" autoFocus {...register('workspaceName')} />
            </FormField>

            <FormField id="r-email" label="Email" required error={errors.email}>
              <Input id="r-email" type="email" placeholder="you@example.com" {...register('email')} />
            </FormField>

            <FormField id="r-name" label="Display name" hint="Optional">
              <Input id="r-name" placeholder="Saurabh" {...register('name')} />
            </FormField>

            <FormField id="r-pw" label="Password" required error={errors.password}>
              <Input id="r-pw" type="password" placeholder="At least 8 characters" {...register('password')} />
            </FormField>

            <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>
              {isSubmitting ? 'Creating…' : 'Create workspace'}
            </Button>

            <p className="text-center text-xs text-content-tertiary">
              Have an account?{' '}
              <Link href="/login" className="text-accent hover:underline">Sign in</Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  );
}
