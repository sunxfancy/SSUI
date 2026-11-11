import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { ConfigService } from '../src/config/configService';
import { server } from './server';

const configUrl = 'http://localhost:7420/config/';

describe('ConfigService', () => {
  it('loads server configuration and writes the startup cache', async () => {
    server.use(
      http.get(configUrl, () => HttpResponse.json({
        ui: { theme: 'dark', auto_open_details: false },
      })),
    );

    const config = await new ConfigService().load();

    expect(config).toMatchObject({ theme: 'dark', auto_open_details: false });
    expect(JSON.parse(localStorage.getItem('ssui.ui_config.v1') || '{}')).toMatchObject(config);
  });

  it('falls back to cached configuration while offline', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    localStorage.setItem('ssui.ui_config.v1', JSON.stringify({ theme: 'light' }));
    server.use(http.get(configUrl, () => HttpResponse.error()));

    await expect(new ConfigService().load()).resolves.toMatchObject({ theme: 'light' });
  });

  it('posts only the requested patch and returns the merged value', async () => {
    let body: unknown;
    server.use(
      http.post(configUrl, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: 'success' });
      }),
    );

    const result = await new ConfigService().save({ auto_open_details: false });

    expect(body).toEqual({ ui: { auto_open_details: false } });
    expect(result.auto_open_details).toBe(false);
  });
});
