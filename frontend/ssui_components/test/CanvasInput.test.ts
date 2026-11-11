import { CanvasInput } from '../src/components/Image/CanvasInput';
import { getComponentsByType } from '../src/components/ComponentsManager';

test('canvas input invokes the current Image loader with the exported PNG path', () => {
    const input = new CanvasInput({ script_path: '/project/workflow.py' });
    input.state = { ...input.state, image: '/project/input/canvas.png' };
    expect(input.onExecute()).toEqual({ function: 'ssui.base.Image.load', params: { path: '/project/input/canvas.png' } });
    expect(getComponentsByType('ssui.base.Image', 'input').some(component => component.name === 'CanvasInput')).toBe(true);
});
