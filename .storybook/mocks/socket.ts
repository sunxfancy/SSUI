/** Static backend /ws session for queue/model stories. Never opens a network connection. */
export class OfflineSocket extends EventTarget {
    readonly url: string;
    readyState = 0;
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onclose: ((event: Event) => void) | null = null;
    constructor(url: string) {
        super();
        this.url = url;
        queueMicrotask(() => {
            if (this.readyState !== 0) return;
            this.readyState = 1;
            const open = new Event('open');
            this.onopen?.(open);
            this.dispatchEvent(open);
            const message = new MessageEvent('message', { data: JSON.stringify({ type: 'uuid', uuid: 'storybook-session' }) });
            this.onmessage?.(message);
            this.dispatchEvent(message);
        });
    }
    send() { throw new Error('[Storybook offline] Supply a provider for outgoing socket messages'); }
    close() {
        this.readyState = 3;
        const event = new Event('close');
        this.onclose?.(event);
        this.dispatchEvent(event);
    }
}
