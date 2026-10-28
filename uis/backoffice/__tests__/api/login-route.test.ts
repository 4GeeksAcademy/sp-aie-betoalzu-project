/** @jest-environment node */

import { POST } from '@/app/api/auth/login/route';
import { proxyAuthRequest } from '@/app/api/auth/_shared';

jest.mock('@/app/api/auth/_shared', () => ({
  proxyAuthRequest: jest.fn(),
}));

const proxy = jest.mocked(proxyAuthRequest);

beforeEach(() => {
  proxy.mockReset();
  proxy.mockResolvedValue(new Response('{}', { status: 200 }));
});

test('forwards credentials only in the JSON body', async () => {
  const credentials = {
    email: 'operator@example.test',
    password: 'synthetic-password',
  };
  const response = await POST(new Request('http://localhost/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  }));

  expect(response.status).toBe(200);
  expect(proxy).toHaveBeenCalledWith('/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
});

test('rejects invalid credential types without forwarding', async () => {
  const response = await POST(new Request('http://localhost/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email: 'operator@example.test', password: 123 }),
  }));

  expect(response.status).toBe(400);
  expect(proxy).not.toHaveBeenCalled();
});
