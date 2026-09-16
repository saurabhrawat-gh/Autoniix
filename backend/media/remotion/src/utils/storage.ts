import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { createReadStream, statSync } from "node:fs";
import { env } from "./env";
import { logger } from "./logger";

let client: S3Client | null = null;

function getClient(): S3Client {
  if (client) return client;
  client = new S3Client({
    region: env.S3_REGION,
    endpoint: env.S3_ENDPOINT || undefined,
    forcePathStyle: env.S3_FORCE_PATH_STYLE,
    credentials:
      env.S3_ACCESS_KEY_ID && env.S3_SECRET_ACCESS_KEY
        ? {
            accessKeyId: env.S3_ACCESS_KEY_ID,
            secretAccessKey: env.S3_SECRET_ACCESS_KEY,
          }
        : undefined,
  });
  return client;
}

export interface UploadResult {
  key: string;
  url: string;
  size: number;
}

/**
 * Uploads a local file to S3/R2 and returns the public URL.
 * Public URL = `${S3_PUBLIC_BASE_URL}/${key}` when configured, otherwise the
 * raw S3 endpoint URL (which may require signed access).
 */
export async function uploadFile(
  localPath: string,
  key: string,
  contentType: string,
): Promise<UploadResult> {
  const size = statSync(localPath).size;
  const body = createReadStream(localPath);

  const prefix = env.S3_KEY_PREFIX.replace(/^\/+|\/+$/g, "");
  const finalKey = prefix && !key.startsWith(`${prefix}/`) ? `${prefix}/${key}` : key;

  logger.info({ key: finalKey, size, contentType }, "uploading to s3");

  await getClient().send(
    new PutObjectCommand({
      Bucket: env.S3_BUCKET,
      Key: finalKey,
      Body: body,
      ContentType: contentType,
    }),
  );

  const url = env.S3_PUBLIC_BASE_URL
    ? `${env.S3_PUBLIC_BASE_URL.replace(/\/$/, "")}/${finalKey}`
    : env.S3_ENDPOINT
      ? `${env.S3_ENDPOINT.replace(/\/$/, "")}/${env.S3_BUCKET}/${finalKey}`
      : `https://${env.S3_BUCKET}.s3.${env.S3_REGION}.amazonaws.com/${finalKey}`;

  return { key: finalKey, url, size };
}
