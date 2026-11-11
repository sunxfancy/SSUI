//! Sparse screen-space cache. Only tiles touched by painted geometry are resident;
//! retained document vectors reconstruct tiles when the camera changes.
use crate::scene::{Scene, SceneObject};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::hash::{Hash, Hasher};

pub const TILE_SIZE: u32 = 256;
pub const GUTTER: u32 = 2;
pub const TILE_EXTENT: u32 = TILE_SIZE + GUTTER * 2;

#[derive(Clone, Debug, Eq, PartialEq, Hash, Ord, PartialOrd)]
pub struct TileKey {
    pub layer: String,
    pub x: i32,
    pub y: i32,
}
pub struct PlannedTile {
    pub key: TileKey,
    pub layer: usize,
    pub objects: Vec<usize>,
    pub signature: u64,
}

// Liang-Barsky clipping avoids walking enormous offscreen stroke coordinates.
fn clip(a: [f32; 2], b: [f32; 2], rect: [f32; 4]) -> Option<([f32; 2], [f32; 2])> {
    let d = [b[0] - a[0], b[1] - a[1]];
    let mut lo = 0f32;
    let mut hi = 1f32;
    for (p, q) in [
        (-d[0], a[0] - rect[0]),
        (d[0], rect[2] - a[0]),
        (-d[1], a[1] - rect[1]),
        (d[1], rect[3] - a[1]),
    ] {
        if p.abs() < 1e-12 {
            if q < 0. {
                return None;
            }
            continue;
        }
        let t = q / p;
        if p < 0. {
            lo = lo.max(t);
        } else {
            hi = hi.min(t);
        }
        if lo > hi {
            return None;
        }
    }
    Some((
        [a[0] + d[0] * lo, a[1] + d[1] * lo],
        [a[0] + d[0] * hi, a[1] + d[1] * hi],
    ))
}

fn segment_tiles(
    a: [f32; 2],
    b: [f32; 2],
    radius: f32,
    size: [u32; 2],
    result: &mut BTreeSet<(i32, i32)>,
) {
    let radius = radius + GUTTER as f32 + 1.;
    let Some((a, b)) = clip(
        a,
        b,
        [
            -radius,
            -radius,
            size[0] as f32 + radius,
            size[1] as f32 + radius,
        ],
    ) else {
        return;
    };
    let steps = (((b[0] - a[0]).abs().max((b[1] - a[1]).abs()) / 128.).ceil() as usize).max(1);
    let cols = size[0].div_ceil(TILE_SIZE) as i32;
    let rows = size[1].div_ceil(TILE_SIZE) as i32;
    if (b[0] - a[0]).abs().max((b[1] - a[1]).abs()) <= TILE_SIZE as f32 {
        let x0 = ((a[0].min(b[0]) - radius) / TILE_SIZE as f32).floor() as i32;
        let x1 = ((a[0].max(b[0]) + radius) / TILE_SIZE as f32).floor() as i32;
        let y0 = ((a[1].min(b[1]) - radius) / TILE_SIZE as f32).floor() as i32;
        let y1 = ((a[1].max(b[1]) + radius) / TILE_SIZE as f32).floor() as i32;
        for y in y0.max(0)..=y1.min(rows - 1) {
            for x in x0.max(0)..=x1.min(cols - 1) {
                if result.contains(&(x, y)) {
                    continue;
                }
                let left = x as f32 * TILE_SIZE as f32;
                let top = y as f32 * TILE_SIZE as f32;
                if clip(
                    a,
                    b,
                    [
                        left - radius,
                        top - radius,
                        left + TILE_SIZE as f32 + radius,
                        top + TILE_SIZE as f32 + radius,
                    ],
                )
                .is_some()
                {
                    result.insert((x, y));
                }
            }
        }
        return;
    }
    let mut candidates = BTreeSet::new();
    for i in 0..=steps {
        let t = i as f32 / steps as f32;
        let p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
        let reach = radius + 128.;
        let min_x = ((p[0] - reach) / TILE_SIZE as f32).floor() as i32;
        let max_x = ((p[0] + reach) / TILE_SIZE as f32).floor() as i32;
        let min_y = ((p[1] - reach) / TILE_SIZE as f32).floor() as i32;
        let max_y = ((p[1] + reach) / TILE_SIZE as f32).floor() as i32;
        for y in min_y.max(0)..=max_y.min(rows - 1) {
            for x in min_x.max(0)..=max_x.min(cols - 1) {
                candidates.insert((x, y));
            }
        }
    }
    for (x, y) in candidates {
        let left = x as f32 * TILE_SIZE as f32;
        let top = y as f32 * TILE_SIZE as f32;
        if clip(
            a,
            b,
            [
                left - radius,
                top - radius,
                left + TILE_SIZE as f32 + radius,
                top + TILE_SIZE as f32 + radius,
            ],
        )
        .is_some()
        {
            result.insert((x, y));
        }
    }
}

fn object_tiles(
    o: &SceneObject,
    size: [u32; 2],
    origin: [f32; 2],
    zoom: f32,
) -> BTreeSet<(i32, i32)> {
    let screen = |x: f32, y: f32| [(x - origin[0]) * zoom, (y - origin[1]) * zoom];
    let mut result = BTreeSet::new();
    match o {
        SceneObject::Stroke {
            stroke,
            feather,
            brush,
            curve,
            ..
        } => {
            let flattened = curve.as_ref().map(|c| c.flatten(0.25 / zoom));
            let points = flattened.as_ref().unwrap_or(&stroke.points);
            for i in 0..points.len() {
                let a = &points[i.saturating_sub(1)];
                let b = &points[i];
                let radius = (stroke.width * brush.pressure(a.pressure.max(b.pressure)) / 2.
                    + feather)
                    * zoom
                    * 1.42;
                segment_tiles(
                    screen(a.x, a.y),
                    screen(b.x, b.y),
                    radius,
                    size,
                    &mut result,
                );
            }
        }
        SceneObject::Image {
            x,
            y,
            width,
            height,
            rotation,
            ..
        } => {
            let (s, c) = rotation.to_radians().sin_cos();
            let corners = [[0., 0.], [*width, 0.], [*width, *height], [0., *height]]
                .map(|p| screen(x + p[0] * c - p[1] * s, y + p[0] * s + p[1] * c));
            let min_x = corners
                .iter()
                .map(|p| p[0])
                .fold(f32::INFINITY, f32::min)
                .max(0.);
            let min_y = corners
                .iter()
                .map(|p| p[1])
                .fold(f32::INFINITY, f32::min)
                .max(0.);
            let max_x = corners
                .iter()
                .map(|p| p[0])
                .fold(f32::NEG_INFINITY, f32::max)
                .min(size[0] as f32);
            let max_y = corners
                .iter()
                .map(|p| p[1])
                .fold(f32::NEG_INFINITY, f32::max)
                .min(size[1] as f32);
            if min_x >= max_x || min_y >= max_y {
                return result;
            }
            for ty in (min_y / TILE_SIZE as f32).floor() as i32
                ..=(max_y / TILE_SIZE as f32).floor() as i32
            {
                for tx in (min_x / TILE_SIZE as f32).floor() as i32
                    ..=(max_x / TILE_SIZE as f32).floor() as i32
                {
                    if tx >= size[0].div_ceil(TILE_SIZE) as i32
                        || ty >= size[1].div_ceil(TILE_SIZE) as i32
                    {
                        continue;
                    }
                    // Separating-axis test: reject blank corners of rotated image bounds.
                    let left = tx as f32 * TILE_SIZE as f32 - GUTTER as f32;
                    let top = ty as f32 * TILE_SIZE as f32 - GUTTER as f32;
                    let tile = [
                        [left, top],
                        [left + TILE_EXTENT as f32, top],
                        [left + TILE_EXTENT as f32, top + TILE_EXTENT as f32],
                        [left, top + TILE_EXTENT as f32],
                    ];
                    let mut intersects = true;
                    for axis in [[1., 0.], [0., 1.], [c, s], [-s, c]] {
                        let dot = |p: &[f32; 2]| p[0] * axis[0] + p[1] * axis[1];
                        let a = corners.map(|p| dot(&p));
                        let b = tile.map(|p| dot(&p));
                        if a.into_iter().fold(f32::INFINITY, f32::min)
                            > b.into_iter().fold(f32::NEG_INFINITY, f32::max)
                            || b.into_iter().fold(f32::INFINITY, f32::min)
                                > a.into_iter().fold(f32::NEG_INFINITY, f32::max)
                        {
                            intersects = false;
                            break;
                        }
                    }
                    if intersects {
                        result.insert((tx, ty));
                    }
                }
            }
        }
    }
    result
}

#[derive(Default)]
pub struct TilePlanner {
    view: Option<[u32; 5]>,
    coverage: HashMap<String, (u64, BTreeSet<(i32, i32)>)>,
}
impl TilePlanner {
    pub fn plan(
        &mut self,
        scene: &Scene,
        size: [u32; 2],
        origin: [f32; 2],
        zoom: f32,
    ) -> Vec<PlannedTile> {
        let view = [
            size[0],
            size[1],
            origin[0].to_bits(),
            origin[1].to_bits(),
            zoom.to_bits(),
        ];
        if self.view != Some(view) {
            self.coverage.clear();
            self.view = Some(view);
        }
        let ids: std::collections::HashSet<_> = scene
            .layers
            .iter()
            .filter(|l| l.visible && l.opacity > 0.)
            .flat_map(|l| l.objects.iter().map(SceneObject::id))
            .collect();
        self.coverage.retain(|id, _| ids.contains(id.as_str()));
        let mut result = Vec::new();
        for (li, layer) in scene.layers.iter().enumerate() {
            if !layer.visible || layer.opacity <= 0. {
                continue;
            }
            let mut tiles: BTreeMap<(i32, i32), (Vec<usize>, bool)> = BTreeMap::new();
            let hashes: Vec<_> = layer.objects.iter().map(SceneObject::fingerprint).collect();
            for (oi, object) in layer.objects.iter().enumerate() {
                let hash = hashes[oi];
                if !self
                    .coverage
                    .get(object.id())
                    .is_some_and(|(key, _)| *key == hash)
                {
                    self.coverage.insert(
                        object.id().into(),
                        (hash, object_tiles(object, size, origin, zoom)),
                    );
                }
                for tile in &self.coverage[object.id()].1 {
                    let entry = tiles.entry(*tile).or_default();
                    entry.0.push(oi);
                    entry.1 |= !object.erase();
                }
            }
            for ((x, y), (objects, has_paint)) in tiles {
                if !has_paint {
                    continue;
                }
                let mut h = std::collections::hash_map::DefaultHasher::new();
                for i in &objects {
                    hashes[*i].hash(&mut h);
                }
                for v in [origin[0], origin[1], zoom] {
                    v.to_bits().hash(&mut h);
                }
                result.push(PlannedTile {
                    key: TileKey {
                        layer: layer.id.clone(),
                        x,
                        y,
                    },
                    layer: li,
                    objects,
                    signature: h.finish(),
                });
            }
        }
        result
    }
}
#[cfg(test)]
fn plan(scene: &Scene, size: [u32; 2], origin: [f32; 2], zoom: f32) -> Vec<PlannedTile> {
    TilePlanner::default().plan(scene, size, origin, zoom)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn scene(points: serde_json::Value) -> Scene {
        serde_json::from_value(serde_json::json!({"layers":[{"id":"ink","visible":true,"opacity":1,"objects":[{"kind":"stroke","stroke":{"id":"s","width":8,"color":[0,0,0,1],"points":points}}]}]})).unwrap()
    }
    #[test]
    fn small_strokes_share_one_tile_and_eraser_alone_allocates_nothing() {
        let mut s =
            scene(serde_json::json!([{"x":30,"y":30,"pressure":1},{"x":70,"y":60,"pressure":1}]));
        assert_eq!(plan(&s, [4096, 4096], [0., 0.], 1.).len(), 1);
        if let SceneObject::Stroke { erase, .. } = &mut s.layers[0].objects[0] {
            *erase = true;
        }
        assert!(plan(&s, [4096, 4096], [0., 0.], 1.).is_empty());
    }
    #[test]
    fn diagonal_does_not_allocate_its_whole_bounding_rectangle() {
        let s = scene(
            serde_json::json!([{"x":20,"y":20,"pressure":1},{"x":4000,"y":4000,"pressure":1}]),
        );
        let tiles = plan(&s, [4096, 4096], [0., 0.], 1.);
        assert!(tiles.len() < 60, "diagonal used {} tiles", tiles.len());
        assert!(tiles.iter().all(|t| (t.key.x - t.key.y).abs() <= 1));
        assert!(plan(&s, [512, 512], [5000., 5000.], 1.).is_empty());
    }
    #[test]
    fn negative_coordinates_crossing_tiles_keep_replay_order() {
        let s = scene(
            serde_json::json!([{"x":-10000,"y":250,"pressure":1},{"x":10000,"y":270,"pressure":1}]),
        );
        let tiles = plan(&s, [512, 512], [0., 0.], 1.);
        assert_eq!(tiles.len(), 4);
        assert!(tiles.iter().all(|t| t.objects == [0]));
    }
    #[test]
    fn coverage_cache_invalidates_on_edit_and_visibility() {
        let mut s =
            scene(serde_json::json!([{"x":30,"y":30,"pressure":1},{"x":70,"y":60,"pressure":1}]));
        let mut planner = TilePlanner::default();
        let before = planner.plan(&s, [1024, 1024], [0., 0.], 1.);
        if let SceneObject::Stroke { stroke, .. } = &mut s.layers[0].objects[0] {
            for p in &mut stroke.points {
                p.x += 512.;
            }
        }
        let after = planner.plan(&s, [1024, 1024], [0., 0.], 1.);
        assert_eq!(before[0].key.x, 0);
        assert_eq!(after[0].key.x, 2);
        s.layers[0].visible = false;
        assert!(planner.plan(&s, [1024, 1024], [0., 0.], 1.).is_empty());
        assert!(planner.coverage.is_empty());
    }
    #[test]
    fn bezier_handles_expand_coverage_beyond_endpoint_bounds() {
        let s:Scene=serde_json::from_value(serde_json::json!({"layers":[{"id":"ink","visible":true,"opacity":1,"objects":[
            {"kind":"stroke","stroke":{"id":"c","points":[],"width":8,"color":[0,0,0,1]},
             "curve":{"nodes":[[20,20,20,20,180,820,0],[600,20,420,820,600,20,1]],"pressure":[[0,0.2],[0.5,1],[1,0.2]],"source_count":1000,"tolerance":0.5}}
        ]}]})).unwrap();
        s.validate().unwrap();
        let tiles = plan(&s, [1024, 1024], [0., 0.], 1.);
        assert!(
            tiles.iter().any(|t| t.key.y == 2),
            "handle bulge was clipped to endpoint bounds"
        );
    }
}
