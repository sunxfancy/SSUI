import { SSUIAIDrawingService } from '../canvas/AIDrawingService';

describe('SSUIAIDrawingService', () => {
  afterEach(() => jest.restoreAllMocks());

  it('submits the executor contract and returns a file URL', async () => {
    const fetchMock = jest.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [{ path: '/fixtures/generated.png' }],
    } as Response);

    const url = await new SSUIAIDrawingService().generateImageUrl(
      '/fixtures/demo.py',
      'generate',
      { prompt: 'test' },
      { Generation: { steps: 20 } },
    );

    expect(url).toBe('/file?path=/fixtures/generated.png');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/execute?script_path=%2Ffixtures%2Fdemo.py&callable=generate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          params: { prompt: 'test' },
          details: { Generation: { steps: 20 } },
        }),
      }),
    );
  });

  it('rejects HTTP failures and invalid result cardinality', async () => {
    jest.spyOn(globalThis, 'fetch').mockResolvedValueOnce({ ok: false } as Response);
    await expect(
      new SSUIAIDrawingService().generateImageUrl('demo.py', 'generate', {}, {}),
    ).rejects.toThrow('API请求失败');

    jest.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response);
    await expect(
      new SSUIAIDrawingService().generateImageUrl('demo.py', 'generate', {}, {}),
    ).rejects.toThrow('返回数据格式错误');
  });
});
