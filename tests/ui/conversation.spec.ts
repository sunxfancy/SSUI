import { test, expect, view } from './fixtures';

const pairType = 'typing.List[typing.Tuple[builtins.str, builtins.str]]';
const chat = {
    params: { model: 'ssui_llm.Text.TextModel', prompt: 'builtins.str', history: `typing.Union[${pairType}, builtins.NoneType]`, system_prompt: 'builtins.str' },
    returns: ['builtins.str', pairType],
    conversation: { prompt_param: 'prompt', context_param: 'history', context_kind: 'pairs', context_output: 1 },
};

test('single context workflow opens chat, sends model/LoRA and roundtrips returned history', async ({ page }) => {
    await page.route('**/api/script?*', route => route.fulfill({ json: { root_path: '', functions: { chat } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    const bodies: any[] = [];
    await page.route('**/api/execute?*', async route => {
        expect(new URL(route.request().url()).searchParams.get('callable')).toBe('chat');
        bodies.push(route.request().postDataJSON());
        // The workflow deliberately normalizes/compacts the history. The UI must
        // send this exact context next time rather than reconstructing its log.
        await route.fulfill({ json: bodies.length === 1
            ? ['你好！我可以帮你完善游戏世界的设定。', [['summary', 'normalized']]]
            : ['可以从角色的目标与冲突开始，再设计一段简短的开场对白。', [['summary', 'normalized'], ['继续', 'second']]] });
    });
    await page.goto(view('conversation', '对话 & #1.py'));
    await expect(page.getByRole('region', { name: '会话', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '运行 chat' })).toHaveCount(0);
    await expect(page.locator('.details-empty')).toBeAttached();
    await page.getByRole('textbox', { name: '文本模型', exact: true }).fill('D:/Models/text');
    await page.getByLabel('LoRA（可选）').fill('D:/Models/lora');
    await page.getByLabel('LoRA 权重').fill('0.8');
    await page.getByText('仅使用本地文件', { exact: true }).click();
    await expect(page.getByRole('checkbox', { name: '仅使用本地文件' })).toBeChecked();
    await page.getByPlaceholder('输入文本').fill('用中文回答');
    const composer = page.getByRole('textbox', { name: '消息', exact: true });
    await composer.fill('你好');
    await composer.press('Enter');
    await expect(page.getByRole('article', { name: '助手，第 1 轮' })).toContainText('游戏世界');
    expect(bodies[0].params).toEqual({ model: { function: 'ssui_llm.Text.TextModel.load', params: {
        model_path: 'D:/Models/text', lora_path: 'D:/Models/lora', lora_weight: 0.8, device: 'auto', local_files_only: true,
    } }, prompt: '你好', history: [], system_prompt: '用中文回答' });
    await composer.fill('继续');
    const saved = page.waitForResponse(response => response.url().includes('/api/ui_state_store') &&
        response.request().method() === 'POST' && Object.values(response.request().postDataJSON().state_data)
            .some((value: any) => value?.chat?.turns?.length === 2));
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 2 轮' })).toContainText('开场对白');
    expect(bodies[1].params.history).toEqual([['summary', 'normalized']]);
    await saved;
    await page.screenshot({ path: 'test-artifacts/conversation/light.png', fullPage: true });
    await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; document.body.classList.add('bp5-dark'); });
    await page.screenshot({ path: 'test-artifacts/conversation/dark.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole('button', { name: '展开设置' })).toBeVisible();
    await expect(composer).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: 'test-artifacts/conversation/mobile.png', fullPage: true });
    // Wait for the existing UI-state service to persist a complete turn.
    await page.reload();
    await expect(page.getByRole('article', { name: '助手，第 2 轮' })).toContainText('开场对白');
    await page.getByRole('button', { name: '新对话' }).click();
    await expect(page.getByRole('article')).toHaveCount(0);
    await page.getByRole('button', { name: '展开设置' }).click();
    await expect(page.getByRole('textbox', { name: '文本模型', exact: true })).toHaveValue('D:/Models/text');
    await composer.fill('重新开始');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 1 轮' })).toBeVisible();
    expect(bodies[2].params.history).toEqual([]);
});

test('failed and malformed replies preserve draft/context, pending requests cannot duplicate', async ({ page }) => {
    const simple = { ...chat, params: { prompt: 'builtins.str', history: pairType } };
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: { chat: simple } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    const bodies: any[] = [];
    await page.route('**/api/execute?*', async route => {
        bodies.push(route.request().postDataJSON());
        if (bodies.length === 1) { await pending; await route.fulfill({ json: { error: '模型加载失败' } }); }
        else if (bodies.length === 2) await route.fulfill({ json: ['bad context', 42] });
        else await route.fulfill({ json: ['recovered', [['hello\nworld', 'recovered']]] });
    });
    await page.goto(view('conversation'));
    await expect(page.locator('.details-empty')).toBeAttached();
    const input = page.getByRole('textbox', { name: '消息', exact: true });
    await input.fill('hello');
    await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true });
    await input.press('Shift+Enter');
    await input.pressSequentially('world');
    expect(bodies).toHaveLength(0);
    await input.press('Enter');
    await expect(input).toBeDisabled();
    await expect(page.getByRole('button', { name: '新对话' })).toBeDisabled();
    release();
    await expect(page.getByRole('alert')).toContainText('模型加载失败');
    await expect(input).toHaveValue('hello\nworld');
    await page.getByRole('button', { name: '重试发送' }).click();
    await expect(page.getByRole('alert')).toContainText('上下文格式不正确');
    await expect(page.getByRole('article')).toHaveCount(0);
    await page.getByRole('button', { name: '重试发送' }).click();
    await expect(page.getByRole('article', { name: '助手，第 1 轮' })).toContainText('recovered');
    expect(bodies.map(body => body.params.history)).toEqual([[], [], []]);
});

test('string context uses the returned context for the next message', async ({ page }) => {
    const meta = { params: { message: 'builtins.str', context: 'builtins.str' }, returns: ['builtins.str', 'builtins.str'],
        conversation: { prompt_param: 'message', context_param: 'context', context_kind: 'text', context_output: 1 } };
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: { chat: meta } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    const bodies: any[] = [];
    await page.route('**/api/execute?*', route => {
        bodies.push(route.request().postDataJSON());
        return route.fulfill({ json: ['answer', 'server context'] });
    });
    await page.goto(view('conversation'));
    await expect(page.locator('.details-empty')).toBeAttached();
    for (let turn = 1; turn <= 2; turn++) {
        await page.getByRole('textbox', { name: '消息', exact: true }).fill('question');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await expect(page.getByRole('article', { name: `助手，第 ${turn} 轮` })).toContainText('answer');
    }
    expect(bodies.map(body => body.params.context)).toEqual(['', 'server context']);
});

test('plain text replies accumulate pair history and changing scripts isolates conversations', async ({ page }) => {
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: { chat: {
        params: { prompt: 'builtins.str', history: pairType }, returns: ['builtins.str'],
        conversation: { ...chat.conversation, context_output: null },
    } } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    const bodies: any[] = [];
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/execute?*', async route => {
        bodies.push(route.request().postDataJSON());
        if (bodies.length === 3) await pending;
        await route.fulfill({ json: ['answer'] }).catch(() => {}); // Navigation aborts the third request.
    });
    await page.goto(view('conversation', 'first.py'));
    await expect(page.locator('.details-empty')).toBeAttached();
    for (let turn = 1; turn <= 2; turn++) {
        await page.getByRole('textbox', { name: '消息', exact: true }).fill(`question ${turn}`);
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await expect(page.getByRole('article', { name: `助手，第 ${turn} 轮` })).toContainText('answer');
    }
    expect(bodies[1].params.history).toEqual([['question 1', 'answer']]);
    await page.getByRole('textbox', { name: '消息', exact: true }).fill('old pending');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByText('正在生成回复…')).toBeVisible();
    await page.goto(view('conversation', 'second.py'));
    release();
    await expect(page.getByText('开始一段对话')).toBeVisible();
    await expect(page.getByRole('article')).toHaveCount(0);
});

test('multiple workflows and text-only functions retain the function console', async ({ page }) => {
    let multiple = true;
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: multiple
        ? { chat, complete: { params: { prompt: 'builtins.str' }, returns: ['builtins.str'] } }
        : { complete: { params: { prompt: 'builtins.str' }, returns: ['builtins.str'] } } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    await page.goto(view('functional'));
    await expect(page.getByRole('button', { name: '运行 chat' })).toBeVisible();
    await expect(page.getByRole('region', { name: '会话', exact: true })).toHaveCount(0);
    multiple = false;
    await page.reload();
    await expect(page.getByRole('button', { name: '运行 complete' })).toBeVisible();
});
