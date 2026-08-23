import { getComponentsByType } from '../src/components/ComponentsManager';

// 触发 ControlNetLoader 模块内的组件注册
import '../src/components/Loader/ControlNetLoader';

describe('ControlNetLoader', () => {
    it('registers loaders for SD1.5 / SDXL / FLUX ControlNet types', () => {
        const sd1 = getComponentsByType('ssui_image.SD1.SD1ControlNet');
        const sdxl = getComponentsByType('ssui_image.SDXL.SDXLControlNet');
        const flux = getComponentsByType('ssui_image.Flux.FluxControlNet');

        expect(sd1.some((c) => c.name === 'SD1ControlNetLoader')).toBe(true);
        expect(sdxl.some((c) => c.name === 'SDXLControlNetLoader')).toBe(true);
        expect(flux.some((c) => c.name === 'FluxControlNetLoader')).toBe(true);
    });

    it('emits a load() call description consumable by ss_executor', () => {
        const registered = getComponentsByType(
            'ssui_image.SD1.SD1ControlNet',
        ).find((c) => c.name === 'SD1ControlNetLoader');
        expect(registered).toBeDefined();

        // 通过 createComponent 拿到一个实例，验证 onExecute 的输出结构
        const element = registered!.createComponent(
            { current: null } as never,
            {
                name: 'control',
                type: 'ssui_image.SD1.SD1ControlNet',
                port: 'input',
                root_path: '',
                script_path: 'examples/basic/workflow-sd1.py',
            },
        );

        // createComponent 返回 React 元素；直接实例化组件类来验证 onExecute
        const Cls = registered!.component as new (props: {
            script_path: string;
        }) => { onExecute(): any };
        const instance = new Cls({ script_path: 'examples/basic/workflow-sd1.py' });
        const result = instance.onExecute();

        expect(result.function).toBe('ssui_image.SD1.SD1ControlNet.load');
        expect(result.params).toHaveProperty('path');
        expect(result.params).toHaveProperty('image_path');
        expect(result.params).toHaveProperty('weight', 1.0);
        expect(element).toBeDefined();
    });
});
