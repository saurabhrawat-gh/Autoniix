import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-surface-0">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="text-5xl font-bold text-accent/40">404</div>
        <h1 className="text-base font-semibold text-content-primary">Page not found</h1>
        <p className="text-xs text-content-tertiary">
          The page you&apos;re looking for doesn&apos;t exist or was moved.
        </p>
        <div className="pt-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
