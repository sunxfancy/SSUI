/** Live MCP commands share the same handlers as the visible UI; no eval channel. */
export interface AgentCommand {
    name: string;
    description: string;
    inputSchema: Record<string, unknown>;
    readOnly?: boolean;
    run: (args: any) => unknown | Promise<unknown>;
}
export const agentObject = (properties: Record<string, unknown> = {}, required = Object.keys(properties)) =>
    ({ type: 'object', properties, required, additionalProperties: false });
export const agentString = { type: 'string', minLength: 1 };
export const agentNumber = { type: 'number' };

export function connectAgent(label: string, commands: AgentCommand[], baseUrl = window.location.origin): () => void {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let socket: WebSocket;
    const handlers = new Map(commands.map(command => [command.name, command]));
    const connect = () => {
        if (stopped) return;
        const url = new URL('/api/agent/connect', baseUrl);
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(url);
        socket.onopen = () => socket.send(JSON.stringify({ label, commands: commands.map(({ run, ...schema }) => schema) }));
        // Serialize commands so state-changing operations cannot race each other.
        let pending = Promise.resolve();
        socket.onmessage = event => {
            const message = JSON.parse(event.data);
            if (message.type !== 'call') return;
            const current = socket;
            pending = pending.then(async () => {
                try {
                    const command = handlers.get(message.command);
                    if (!command) throw new Error('Unknown command');
                    const result = await command.run(message.arguments);
                    await new Promise(resolve => setTimeout(resolve, 0));
                    if (current.readyState === WebSocket.OPEN) current.send(JSON.stringify({ id: message.id, result: result ?? null }));
                } catch (error) {
                    if (current.readyState === WebSocket.OPEN) current.send(JSON.stringify({ id: message.id, error: String(error) }));
                }
            });
        };
        socket.onclose = () => { if (!stopped) timer = setTimeout(connect, 2000); };
        socket.onerror = () => socket.close();
    };
    connect();
    return () => { stopped = true; clearTimeout(timer); socket?.close(); };
}

/** DOM fallback covers menus, forms, previews, settings and extension controls. */
export function agentDOMCommands(root: Document = document): AgentCommand[] {
    let elements = new Map<string, HTMLElement>();
    let revision = 0;
    const get = (id: string) => {
        const element = elements.get(id);
        if (!element?.isConnected) throw new Error('Stale element; take ui.snapshot again');
        if (element.matches(':disabled,[aria-disabled="true"]')) throw new Error('Element is disabled');
        return element;
    };
    return [{ name: 'ui.snapshot', description: 'Inspect live visible controls and text; IDs last until the next snapshot. Password values omitted.',
        readOnly: true, inputSchema: agentObject(), run: () => {
            elements = new Map(); revision++;
            const controls = Array.from(root.querySelectorAll<HTMLElement>('button,input,textarea,select,a,canvas,video,audio,model-viewer,[role="button"],[role="tab"],[role="menuitem"],[contenteditable="true"]'))
                .filter(element => element.getClientRects().length > 0 || (element instanceof HTMLInputElement && element.type === 'file')).slice(0, 2000).map((element, index) => {
                    const id = `${revision}:${index}`; elements.set(id, element);
                    return { id, tag: element.tagName, role: element.getAttribute('role'), text: element.innerText?.slice(0, 300),
                        label: element.getAttribute('aria-label') || element.getAttribute('placeholder') || element.getAttribute('title'),
                        type: element.getAttribute('type'), disabled: element.matches(':disabled,[aria-disabled="true"]'),
                        bounds: element.getBoundingClientRect().toJSON(),
                        value: element instanceof HTMLInputElement && element.type === 'password' ? undefined : (element as HTMLInputElement).value };
                });
            return { title: root.title, url: root.location.href, text: root.body.innerText.slice(0, 20000), controls };
        } },
        { name: 'ui.click', description: 'Click a visible control from ui.snapshot.', inputSchema: agentObject({ id: agentString }),
            run: async ({ id }) => { get(id).click(); await new Promise(resolve => setTimeout(resolve, 0)); return { clicked: id }; } },
        { name: 'ui.input', description: 'Set a live text/select/checkbox value using native setters and React input/change events.',
            inputSchema: agentObject({ id: agentString, value: { type: ['string', 'boolean'] } }), run: async ({ id, value }) => {
                const element = get(id);
                if (element instanceof HTMLInputElement && ['checkbox', 'radio'].includes(element.type)) {
                    if (element.checked !== value) element.click();
                } else if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
                    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set?.call(element, String(value));
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (element.isContentEditable) { element.textContent = String(value); element.dispatchEvent(new Event('input', { bubbles: true })); }
                else throw new Error('Control is not editable');
                await new Promise(resolve => setTimeout(resolve, 0));
                return { changed: id };
            } },
        { name: 'ui.key', description: 'Send a key to a current control or document (e.g. Escape, Delete, Enter, Ctrl+z).',
            inputSchema: agentObject({ key: agentString, id: { type: 'string' }, ctrlKey: { type: 'boolean' }, shiftKey: { type: 'boolean' } }, ['key']),
            run: ({ id, ...event }) => { const target = id ? get(id) : root; target.dispatchEvent(new KeyboardEvent('keydown', { ...event, bubbles: true })); return true; } },
        { name: 'ui.pointer', description: 'Send pointer/context-menu/wheel events to a visible canvas/control; coordinates are viewport pixels from snapshot bounds.',
            inputSchema: agentObject({ id: agentString, type: { enum: ['pointerdown', 'pointermove', 'pointerup', 'mousedown', 'mousemove', 'mouseup', 'contextmenu', 'wheel'] },
                x: agentNumber, y: agentNumber, button: { type: 'integer', minimum: 0, maximum: 2 }, pressure: { type: 'number', minimum: 0, maximum: 1 },
                deltaY: agentNumber, shiftKey: { type: 'boolean' }, ctrlKey: { type: 'boolean' } }, ['id', 'type', 'x', 'y']),
            run: ({ id, type, x, y, deltaY = 0, ...options }) => {
                const element = get(id); const common = { clientX: x, clientY: y, bubbles: true, cancelable: true, ...options };
                element.dispatchEvent(type === 'wheel' ? new WheelEvent(type, { ...common, deltaY }) : type === 'contextmenu' || type.startsWith('mouse') ? new MouseEvent(type, common) : new PointerEvent(type, { ...common, pointerId: 1, pointerType: 'mouse', buttons: type === 'pointerup' ? 0 : 1 })); return true;
            } },
        { name: 'ui.upload', description: 'Set an HTML file input using a base64 file and dispatch its existing change handler.',
            inputSchema: agentObject({ id: agentString, filename: agentString, data_base64: { type: 'string', maxLength: 28000000 }, mimeType: agentString }),
            run: ({ id, filename, data_base64, mimeType }) => { const element = get(id); if (!(element instanceof HTMLInputElement) || element.type !== 'file') throw new Error('Expected file input');
                const bytes = Uint8Array.from(atob(data_base64), c => c.charCodeAt(0)); const transfer = new DataTransfer();
                transfer.items.add(new File([bytes], filename, { type: mimeType })); element.files = transfer.files;
                element.dispatchEvent(new Event('change', { bubbles: true })); return true;
            } },
    ];
}
