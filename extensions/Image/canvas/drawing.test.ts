import { hitStroke, smoothPoints } from './drawing';
import type { Layer } from './types';
import { BRUSHES, brushPressure } from './brushes';
const layers = (): Layer[] => [{ id: 'layer', name: 'Ink', visible: true, locked: false, opacity: 1, objects: [
            { id: 'stroke', type: 'stroke', x: 100, y: 100, rotation: 90, strokeWidth: 10,
                points: [{ x: 0, y: 0, pressure: 0.2 }, { x: 100, y: 0, pressure: 1 }] }
        ] }];
test('hit testing uses object transforms and pressure', () => {
    const doc = layers();
    expect(hitStroke(doc, 100, 180, 0)?.object.id).toBe('stroke');
    expect(hitStroke(doc, 104, 100, 0)).toBeNull();
    expect(hitStroke(doc, 104, 200, 0)?.object.id).toBe('stroke');
});
test('hidden and locked layers are not editable; images above strokes block picking', () => {
    const doc = layers();
    doc[0].locked = true;
    expect(hitStroke(doc, 100, 180, 0)).toBeNull();
    doc[0].locked = false;
    doc[0].visible = false;
    expect(hitStroke(doc, 100, 180, 0)).toBeNull();
    doc[0].visible = true;
    doc[0].objects.push({ id: 'image', type: 'image', x: 80, y: 160, width: 50, height: 50 });
    expect(hitStroke(doc, 100, 180, 0)).toBeNull();
});
test('smoothing reduces a spike while preserving endpoints and pressure', () => {
    const points = [{ x: 0, y: 0, pressure: 0.2 }, { x: 10, y: 20, pressure: 0.6 }, { x: 20, y: 0, pressure: 1 }];
    const next = smoothPoints(points);
    expect(next[0]).toEqual(points[0]);
    expect(next[2]).toEqual(points[2]);
    expect(next[1]).toEqual({ x: 10, y: 10, pressure: 0.6 });
    expect(points[1].y).toBe(20);
});
test('new brushes have distinct pressure responses and marker remains pickable at low pressure', () => {
    expect(BRUSHES.map(b=>b.id)).toEqual(expect.arrayContaining(['pen','marker','watercolor','pencil']));
    expect(brushPressure('marker',0)).toBeCloseTo(0.8);
    expect(brushPressure('pen',0.1)).toBeGreaterThan(0.1);
    const doc=layers();doc[0].objects[0].strokeStyle='marker';
    doc[0].objects[0].points!.forEach(p=>{p.pressure=0;});
    expect(hitStroke(doc,103,180,0)?.object.id).toBe('stroke');
});
