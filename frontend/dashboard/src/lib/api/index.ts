/**
 * API client barrel — re-exports all domain modules.
 * Import from here: `import { channelsApi } from '@/lib/api'`
 *
 * For backwards compatibility, `api-v2.ts` also re-exports everything from
 * this barrel so existing `import ... from '../api-v2'` paths keep working.
 */

export * from './client';
export * from './flags';
export * from './auth';
export * from './channels';
export * from './dashboard';
export * from './providers';
export * from './content';
export * from './experiments';
export * from './library';
export * from './review';
export * from './notifications';
export * from './users';
export * from './workspace';
export * from './jobs';
export * from './system';
export * from './lookup';
export * from './voice';
export * from './query-keys';
