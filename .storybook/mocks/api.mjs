/** Storybook-only transport. Routes are METHOD + pathname (query is available to handlers). */
export function createOfflineApi(nativeFetch, origin, allowLocalTestServer = () => false) {
    let scenario = {};
    return {
        configure(value = {}) { scenario = value; },
        async fetch(input, init = {}) {
            const url = new URL(typeof input === 'string' ? input : input.url ?? input.href, origin);
            if (url.protocol === 'data:' || url.protocol === 'blob:') return nativeFetch(input, init);
            if (allowLocalTestServer() && url.origin === 'http://127.0.0.1:7422') {
                return nativeFetch(input, init);
            }
            const method = (init.method ?? input.method ?? 'GET').toUpperCase();
            const business = /^\/(api(?:\/|$)|files?(?:\/|$)|config(?:\/|$)|extension(?:\/|$))/.test(url.pathname);
            const key = `${method} ${url.pathname}`;
            const route = scenario.routes?.[key];
            // Only Storybook's own assets may reach the network.
            if (!business && route === undefined && url.origin === origin) return nativeFetch(input, init);
            const signal = init.signal ?? input.signal;
            signal?.throwIfAborted();
            if (scenario.delay) await new Promise((resolve, reject) => {
                const timer = setTimeout(done, scenario.delay);
                function done() { signal?.removeEventListener('abort', abort); resolve(); }
                function abort() { clearTimeout(timer); reject(signal.reason); }
                signal?.addEventListener('abort', abort, { once: true });
            });
            signal?.throwIfAborted();
            if (route === undefined) throw new Error(`[Storybook offline] Missing mock: ${key}`);
            const result = typeof route === 'function' ? await route({ url, input, init }) : route;
            return result instanceof Response ? result : Response.json(result);
        },
    };
}
