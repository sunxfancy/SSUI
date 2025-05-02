export interface AIDrawingService {
    /**
     * 初始化AI绘图服务
     */
    initialize(): Promise<void>;

    /**
     * 根据指定的区域生成图像
     * @param x 区域左上角x坐标
     * @param y 区域左上角y坐标
     * @param width 区域宽度
     * @param height 区域高度
     * @param prompt 生成提示词
     */
    generateImage(x: number, y: number, width: number, height: number, prompt: string): Promise<ImageData>;
}

/**
 * 模拟AI绘图服务的实现，用于测试
 */
export class MockAIDrawingService implements AIDrawingService {
    async initialize(): Promise<void> {
        console.log('Mock AI Drawing Service initialized');
    }

    async generateImage(x: number, y: number, width: number, height: number, prompt: string): Promise<ImageData> {
        console.log(`Generating image at (${x}, ${y}) with size ${width}x${height} using prompt: ${prompt}`);
        // 创建一个简单的测试图像
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('Failed to get canvas context');
        
        // 绘制一个简单的测试图案
        ctx.fillStyle = '#f0f0f0';
        ctx.fillRect(0, 0, width, height);
        ctx.strokeStyle = '#000000';
        ctx.strokeRect(0, 0, width, height);
        ctx.fillStyle = '#ff0000';
        ctx.fillText('Mock AI Generated', 10, 20);
        
        return ctx.getImageData(0, 0, width, height);
    }
} 