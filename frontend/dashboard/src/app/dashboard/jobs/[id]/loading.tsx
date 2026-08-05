import { SkeletonCard } from '@/lib/components/Skeleton';

export default function JobLoading() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  );
}
