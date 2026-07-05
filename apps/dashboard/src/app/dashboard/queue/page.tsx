'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function QueueRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace('/dashboard/progress'); }, [router]);
  return null;
}
