import type { paths } from './schema';

type Action = 'interpret' | 'assess';
type Endpoint<A extends Action> = paths[`/api/${A}`]['post'];
type Payload<A extends Action> = Endpoint<A>['requestBody']['content']['application/json'];
type Result<A extends Action> = Endpoint<A>['responses'][200]['content']['application/json'];

export class RequestError extends Error {
  constructor(public readonly requestId: string | null) {
    super('API request failed');
  }
}

export async function post<A extends Action>(action: A, data: Payload<A>) {
  const response = await fetch(`/api/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  });
  const requestId = response.headers.get('x-request-id');
  if (!response.ok) throw new RequestError(requestId);
  return { data: await response.json() as Result<A>, requestId };
}
