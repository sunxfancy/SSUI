export interface AIDrawingService {
    /**
     * 初始化AI绘图服务
     */
    initialize(script: string, callable:string, args:any, details:any): Promise<{width:number, height:number}>;

    /**
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

    // 根据指定的区域生成图像
    async generateImage(script: string, callable:string, args:any, details:any): Promise<ImageData> {
        return new ImageData(new Uint8ClampedArray([255, 0, 0, 255]), 512, 512);
    }
} 