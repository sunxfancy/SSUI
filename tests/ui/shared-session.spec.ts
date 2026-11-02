import { test, expect } from './fixtures';

test('three independent views share context and settings, including edit/reset and failures', async ({ page }) => {
    const history = 'typing.List[typing.Tuple[builtins.str, builtins.str]]';
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: { chat: {
        params: { prompt: 'builtins.str', history, model: 'ssui_llm.Text.TextModel' }, returns: ['builtins.str', history],
        conversation: { prompt_param: 'prompt', context_param: 'history', context_kind: 'pairs', context_output: 1 },
    } } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    await page.route('**/file/text?*', route => route.fulfill({ json: { content: '# shared workflow', version: 'v1' } }));
    const bodies: any[] = [];
    let fail = false;
    await page.route('**/api/execute?*', route => {
        const body = route.request().postDataJSON(); bodies.push(body);
        return route.fulfill({ json: fail ? { error: 'failed run' } : ['answer ' + body.params.prompt,
            [...body.params.history, [body.params.prompt, 'answer ' + body.params.prompt]]] });
    });
    await page.goto('/functional_ui/?path=' + encodeURIComponent('共享 & #1.py'));
    await expect(page.getByRole('region', { name: '会话', exact: true })).toBeVisible();
    expect(new URL(page.url()).searchParams.get('view')).toBe('conversation');
    await expect(page.locator('.details-empty')).toBeAttached();
    await page.getByRole('textbox', { name: '文本模型', exact: true }).fill('D:/Models/text');
    await page.getByLabel('LoRA（可选）').fill('D:/Models/lora');
    await page.getByRole('textbox', { name: '消息', exact: true }).fill('first');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 1 轮' })).toContainText('answer first');
    // Switch immediately, without waiting for persistence debounce.
    await page.getByRole('button', { name: 'Functional UI', exact: true }).click();
    await expect(page.getByRole('button', { name: '运行 chat' })).toBeVisible();
    await expect(page.getByRole('region', { name: '会话', exact: true })).toHaveCount(0);
    await expect(page.getByRole('textbox', { name: '文本模型', exact: true })).toHaveValue('D:/Models/text');
    await expect(page.getByLabel('LoRA（可选）')).toHaveValue('D:/Models/lora');
    await page.getByRole('button', { name: '查看／编辑上下文' }).click();
    expect(JSON.parse(await page.getByRole('textbox', { name: '上下文', exact: true }).inputValue())).toEqual([['first', 'answer first']]);
    await page.getByRole('textbox', { name: '上下文', exact: true }).fill('invalid');
    await page.getByRole('button', { name: '保存上下文' }).click();
    await expect(page.getByRole('alert')).toContainText('有效上下文');
    await page.getByRole('textbox', { name: '上下文', exact: true }).fill('[["edited","context"]]');
    await page.getByRole('button', { name: '保存上下文' }).click();
    await page.getByPlaceholder('输入文本', { exact: true }).fill('second');
    await page.getByRole('button', { name: '运行 chat' }).click();
    await expect(page.getByText('共享会话 · 2 轮', { exact: false })).toBeVisible();
    expect(bodies[1].params.history).toEqual([['edited', 'context']]);
    fail = true;
    await page.getByRole('button', { name: '运行 chat' }).click();
    await expect(page.getByRole('alert')).toContainText('failed run');
    fail = false;
    await page.getByRole('button', { name: 'Code Editor', exact: true }).click();
    await expect(page.locator('.code-editor-status')).toHaveText('Ready');
    await page.getByRole('button', { name: '会话 UI', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 2 轮' })).toContainText('answer second');
    await expect(page.getByRole('article')).toHaveCount(4);
    await page.reload();
    await expect(page.getByRole('article', { name: '助手，第 2 轮' })).toContainText('answer second');
    await page.getByRole('textbox', { name: '消息', exact: true }).fill('third');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 3 轮' })).toContainText('answer third');
    expect(bodies[3].params.history).toEqual([['edited', 'context'], ['second', 'answer second']]);
    await page.getByRole('button', { name: 'Functional UI', exact: true }).click();
    await page.getByRole('button', { name: '重置上下文' }).click();
    await page.getByRole('button', { name: '会话 UI', exact: true }).click();
    await expect(page.getByRole('article')).toHaveCount(0);
    await page.getByRole('textbox', { name: '消息', exact: true }).fill('new');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByRole('article', { name: '助手，第 1 轮' })).toContainText('answer new');
    expect(bodies[4].params.history).toEqual([]);
    await page.screenshot({ path: 'test-artifacts/conversation/three-views.png', fullPage: true });
});

test('explicit functional choice is honored; incompatible chat remains switchable', async ({ page }) => {
    await page.route('**/api/script?*', route => route.fulfill({ json: { functions: { complete: { params: {}, returns: [] } } } }));
    await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
    await page.goto('/functional_ui/?path=test.py&view=conversation');
    await expect(page.getByText('此脚本不支持会话视图')).toBeVisible();
    await page.getByRole('button', { name: 'Functional UI', exact: true }).click();
    await expect(page.getByRole('button', { name: '运行 complete' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('button', { name: '运行 complete' })).toBeVisible();
});
