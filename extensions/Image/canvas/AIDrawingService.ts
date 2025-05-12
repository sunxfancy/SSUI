export interface AIDrawingService {
    /**
     * 初始化AI绘图服务
     */
    initialize(script: string, callable:string, args:any, details:any): Promise<{width:number, height:number}>;


    /**
     * 生成图像的URL
     */
    generateImageUrl(script: string, callable:string, args:any, details:any): Promise<string>;

    /**
     * 生成图像
     */
    generateImage(script: string, callable:string, args:any, details:any): Promise<ImageData>;
}



/**
 * 模拟AI绘图服务的实现，用于测试
 */
export class SSUIAIDrawingService implements AIDrawingService {
    // 调用前先调用这个函数，执行一下获取生成图像的尺寸
    async initialize(script: string, callable:string, args:any, details:any): Promise<{width:number, height:number}> {
        return {width: 512, height: 512};
    }

    // 生成图像的URL
    async generateImageUrl(script: string, callable:string, args:any, details:any): Promise<string> {
        const res = await fetch('/api/execute?' + new URLSearchParams({
            script_path: script,
            callable: callable,
        }), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ params: args, details: details }),
        });

        if (!res.ok) {
            throw new Error('API请求失败');
        }

        const data = await res.json();
        if (data.length !== 1) {
            throw new Error('返回数据格式错误');
        }

        const url = '/file?path=' + data[0].path;
        return url;
    }

    // 根据指定的区域生成图像
    async generateImage(script: string, callable:string, args:any, details:any): Promise<ImageData> {
        const url = await this.generateImageUrl(script, callable, args, details);
        const imageRes = await fetch(url);
        if (!imageRes.ok) {
            throw new Error('图像下载失败');
        }

        const blob = await imageRes.blob();
        return await this.blobToImageData(blob);
    }

    private blobToImageData(blob: Blob): Promise<ImageData> {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    ctx.drawImage(img, 0, 0);
                    const imageData = ctx.getImageData(0, 0, img.width, img.height);
                    resolve(imageData);
                } else {
                    reject(new Error('无法获取canvas上下文'));
                }
            };
            img.onerror = () => reject(new Error('图像加载失败'));
            img.src = URL.createObjectURL(blob);
        });
    }
} 