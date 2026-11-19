import { trackedFetch } from './activityClient';
import type { paths } from './schema';

type Action = 'interpret' | 'assess';
type Endpoint<A extends Action> = paths[`/api/${A}`]['post'];
type Payload<A extends Action> = Endpoint<A>['requestBody']['content']['application/json'];
type Result<A extends Action> = Endpoint<A>['responses'][200]['content']['application/json'];

export class RequestError extends Error {
  constructor(
    public readonly requestId: string | null,
    public readonly retryAfter?: number,
    public readonly detail?: string,
  ) {
    super(detail ?? 'API request failed');
  }
}

function attemptSummary(result: unknown) {
  if (!result || typeof result !== 'object') return {};
  const data = result as Record<string, unknown>;
  if ('rule' in data) return { decision: data.status, rule: data.rule, policyVersion: data.version };
  if ('surface' in data) return {
    surface: data.surface, materials: data.materials, method: data.method, surfaceTerm: data.surface_term,
    translatedText: data.translated_text, translationProvider: data.translation_provider,
    objectType: data.object_type, device: data.device, substrate: data.substrate, finish: data.finish,
  };
  if ('result' in data) return { result: data.result };
  return {};
}

async function parseJSON<T>(response: Response): Promise<T> {
  const requestId = response.headers.get('x-request-id');
  const body: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const seconds = Number(response.headers.get('retry-after'));
    const retryAfter = response.status === 429 && Number.isInteger(seconds) && seconds > 0 ? seconds : undefined;
    const detail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
      ? body.detail : undefined;
    throw new RequestError(requestId, retryAfter, detail);
  }
  if (body === undefined) throw new RequestError(requestId);
  return body as T;
}

export async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, cache: 'no-store' });
  return parseJSON<T>(response);
}

export async function requestJSON<T>(path: string, payload: unknown, originalText: string, action: string) {
  const started = performance.now();
  let response: Response | undefined;
  let requestId: string | null = null;
  let retryAfter: number | undefined;
  let result: T | undefined;
  try {
    response = await trackedFetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), cache: 'no-store',
    });
    requestId = response.headers.get('x-request-id');
    result = await parseJSON<T>(response);
    return { data: result, requestId };
  } catch (error) {
    if (error instanceof RequestError) retryAfter = error.retryAfter;
    throw error instanceof RequestError ? error : new RequestError(requestId);
  } finally {
    console.info({
      event: 'homechem.attempt', action, originalText, locale: document.documentElement.lang,
      requestId, httpStatus: response?.status ?? null,
      elapsedMs: Math.round(performance.now() - started),
      outcome: result === undefined ? 'error' : 'success',
      ...(retryAfter !== undefined && { retryAfter }),
      ...attemptSummary(result),
    });
  }
}

export function post<A extends Action>(action: A, data: Payload<A>, originalText: string) {
  return requestJSON<Result<A>>(`/api/${action}`, data, originalText, action);
}
