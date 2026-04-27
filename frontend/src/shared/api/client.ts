import { z } from 'zod'
import { env } from '../config/env'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(message)
  }
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodSchema<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    },
  })
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiError(errorMessage(payload, '请求失败'), response.status, payload)
  }

  return schema.parse(payload)
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
  schema: z.ZodSchema<T>,
): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method: 'POST',
    body: formData,
  })
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiError(errorMessage(payload, '上传失败'), response.status, payload)
  }

  return schema.parse(payload)
}

function errorMessage(payload: unknown, fallback: string): string {
  if (
    payload &&
    typeof payload === 'object' &&
    'detail' in payload &&
    typeof payload.detail === 'string'
  ) {
    return payload.detail
  }
  return fallback
}
