

export class ExtensionLoader {
    public async loadExtensions() {
        let response = await fetch('/api/extensions');
        if (!response.ok) {
            throw new Error('Failed to fetch extensions');
        }
        let data = await response.json();
        // for (let key of Object.keys(data)) {
        //     let script = document.createElement('script');
        //     script.src = 'http://' + window.location.host + data[key];
        //     script.type='module';
        //     script.setAttribute('name', key);
        //     document.head.appendChild(script);
        //     this.extensions.set(key, script);
        // }
    }

    private extensions = new Map<string, HTMLScriptElement>();
    
}