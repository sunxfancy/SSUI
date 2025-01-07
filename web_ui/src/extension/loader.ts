
type ExtensionMeta = {
    name: string;
    js_url: string;
}

class ExtensionLoader {
    public async loadExtensions() {
        let response = await fetch('/api/extensions');
        if (!response.ok) {
            throw new Error('Failed to fetch extensions');
        }
        let data = await response.json() as ExtensionMeta[];
        for (let meta of data) {
            let script = document.createElement('script');
            script.src = window.location.host + meta.js_url;
            script.setAttribute('name', meta.name);
            document.head.appendChild(script);
            this.extensions.set(meta.name, script);
        }
    }

    private extensions = new Map<string, HTMLScriptElement>();
    
}