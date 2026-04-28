import { z } from 'zod'
import { env } from '../config/env'

const REQUEST_TIMEOUT_MS = 120000
const UPLOAD_TIMEOUT_MS = 30000

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
  const response = await fetchWithTimeout(`${env.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    },
  }, REQUEST_TIMEOUT_MS)
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
  const response = await fetchWithTimeout(`${env.apiBaseUrl}${path}`, {
    method: 'POST',
    body: formData,
  }, UPLOAD_TIMEOUT_MS)
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiError(errorMessage(payload, '上传失败'), response.status, payload)
  }

  return schema.parse(payload)
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(
        '后端服务响应超时，请确认 API 服务正在运行并重启已卡住的后端进程。',
        0,
        null,
      )
    }
    throw new ApiError('无法连接后端服务，请确认 API 服务和 Vite 代理配置。', 0, null)
  } finally {
    window.clearTimeout(timeout)
  }
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
