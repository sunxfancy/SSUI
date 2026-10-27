import { MotionData, MotionClipPreview, projectPoint, validateMotion } from '../src/components/Motion/MotionClipPreview';
import { getComponentsByType } from '../src/components/ComponentsManager';

const motion: MotionData = { schema: 'ssui.motion.clip/v1', fps: 30, units: 'meters', coordinate_system: 'Y-up;+Z-forward',
    joint_names: ['root', 'hand'], parents: [-1, 0], positions: [[[0, 0, 0], [1, 1, 0]], [[0, 0, 1], [1, 2, 1]]] };

describe('generated 3D motion', () => {
    it('registers a dedicated motion output', () => {
        expect(getComponentsByType('ssui.base.MotionClip', 'output').some(c => c.component === MotionClipPreview)).toBe(true);
    });
    it('rejects corrupt coordinates and hierarchy instead of drawing them', () => {
        expect(validateMotion(motion)).toBe(motion);
        expect(() => validateMotion({ ...motion, parents: [-1, 1] })).toThrow();
        expect(() => validateMotion({ ...motion, positions: [[[NaN, 0, 0]]] })).toThrow();
        expect(() => validateMotion({ ...motion, positions: [] })).toThrow();
    });
    it('uses depth when rotating the 3D camera', () => {
        const front = projectPoint([0, 0, 1], [0, 0, 0], 1, 0);
        const side = projectPoint([0, 0, 1], [0, 0, 0], 1, 90);
        expect(front[0]).toBe(200);
        expect(side[0]).toBeCloseTo(330);
    });
    it('stops playback timers on unmount', () => {
        jest.useFakeTimers();
        const preview = new MotionClipPreview({});
        preview.state = { data: motion, index: 0, yaw: 0, playing: false, loading: false, followRoot: true, zoom: 1 };
        preview.setState = jest.fn();
        preview.togglePlayback();
        expect(jest.getTimerCount()).toBe(1);
        preview.componentWillUnmount();
        expect(jest.getTimerCount()).toBe(0);
        jest.useRealTimers();
    });
});
