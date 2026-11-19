export async function trackedFetch(path: string, options: RequestInit = {}) {
  const requestedKey = crypto.randomUUID().replaceAll('-', '');
  const headers = new Headers(options.headers);
  headers.set('X-Activity-Key', requestedKey);
  const notify = (running: boolean, key = requestedKey) => window.dispatchEvent(
    new CustomEvent('homechem.activity', { detail: { requestedKey, key, running } }),
  );
  notify(true);
  try {
    const response = await fetch(path, { ...options, headers });
    notify(false, response.headers.get('X-Activity-ID') ?? requestedKey);
    return response;
  } catch (error) {
    notify(false);
    throw error;
  }
}
