/** @jest-environment node */

import { proxyToRecordsBackend } from '@/app/api/records/_shared';

afterEach(() => {
  jest.restoreAllMocks();
});

test.each(['Authorization', 'authorization', 'AUTHORIZATION'])(
  'does not forward local credentials with header %s to the public provider',
  async (header) => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
      new Response('[]', { headers: { 'Content-Type': 'application/json' } }),
    );

    const response = await proxyToRecordsBackend('/records', {
      method: 'GET',
      headers: {
        [header]: 'Bearer synthetic-local-token',
        Cookie: 'synthetic-cookie=value',
      },
    });

    expect(response.status).toBe(200);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('https://playground.4geeks.com/tracker/api/v1/records');
    const forwarded = new Headers(options?.headers);
    expect(forwarded.has('authorization')).toBe(false);
    expect(forwarded.has('cookie')).toBe(false);
    expect(forwarded.get('content-type')).toBe('application/json');
  },
);
