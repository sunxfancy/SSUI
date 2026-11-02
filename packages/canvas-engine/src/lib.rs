//! Editable vector source data; GPU meshes are disposable derived data.
mod brush;
mod curve;
pub use curve::CurvePath;
mod render;
mod scene;
mod tiles;
pub use brush::Brush;
use lyon_tessellation::{
    math::point, path::Path, BuffersBuilder, LineCap, LineJoin, StrokeOptions, StrokeTessellator,
    StrokeVertex, VertexBuffers,
};
pub use render::Renderer;
pub use scene::{Scene, SceneLayer, SceneObject, SceneRenderer, SceneUpdate};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Sample {
    pub x: f32,
    pub y: f32,
    pub pressure: f32,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Stroke {
    pub id: String,
    pub points: Vec<Sample>,
    pub width: f32,
    /// Straight RGBA, in the range 0..=1.
    pub color: [f32; 4],
}
impl Stroke {
    pub fn validate_style(&self) -> Result<(), String> {
        if self.id.is_empty()
            || !self.width.is_finite()
            || self.width <= 0.
            || !self.color.iter().copied().all(unit)
        {
            return Err("Invalid stroke style".into());
        }
        Ok(())
    }
    pub fn validate(&self) -> Result<(), String> {
        if self.id.is_empty()
            || self.points.is_empty()
            || !self.width.is_finite()
            || self.width <= 0.0
            || !self.color.iter().copied().all(unit)
            || !self
                .points
                .iter()
                .all(|p| p.x.is_finite() && p.y.is_finite() && unit(p.pressure))
        {
            return Err("Invalid stroke ID, geometry or color".into());
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Layer {
    pub id: String,
    pub name: String,
    pub visible: bool,
    pub locked: bool,
    /// Layer opacity is applied at composition time, not to individual strokes.
    pub opacity: f32,
    pub strokes: Vec<Stroke>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Document {
    pub version: u32,
    pub layers: Vec<Layer>,
}

impl Document {
    pub fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err("Unsupported document version".into());
        }
        let mut ids = std::collections::HashSet::new();
        for layer in &self.layers {
            if layer.id.is_empty() || !ids.insert(&layer.id) || !unit(layer.opacity) {
                return Err("Invalid layer ID or opacity".into());
            }
            for stroke in &layer.strokes {
                stroke.validate()?;
                if !ids.insert(&stroke.id) {
                    return Err("Duplicate stroke ID".into());
                }
            }
        }
        Ok(())
    }
    /// Returns the topmost editable stroke, using pressure-aware segment distance.
    pub fn hit_test(&self, x: f32, y: f32, tolerance: f32) -> Option<String> {
        if !x.is_finite() || !y.is_finite() || !tolerance.is_finite() || tolerance < 0.0 {
            return None;
        }
        for layer in self
            .layers
            .iter()
            .rev()
            .filter(|l| l.visible && !l.locked && l.opacity > 0.0)
        {
            for s in layer.strokes.iter().rev().filter(|s| s.color[3] > 0.0) {
                let hit = |a: &Sample, b: &Sample| {
                    let dx = b.x - a.x;
                    let dy = b.y - a.y;
                    let length = dx * dx + dy * dy;
                    let t = if length > 0.0 {
                        (((x - a.x) * dx + (y - a.y) * dy) / length).clamp(0.0, 1.0)
                    } else {
                        0.0
                    };
                    let pressure = a.pressure + (b.pressure - a.pressure) * t;
                    (x - a.x - dx * t).hypot(y - a.y - dy * t)
                        <= tolerance + s.width * pressure.max(0.01) / 2.0
                };
                if s.points.windows(2).any(|w| hit(&w[0], &w[1]))
                    || (s.points.len() == 1 && hit(&s.points[0], &s.points[0]))
                {
                    return Some(s.id.clone());
                }
            }
        }
        None
    }
}
fn unit(v: f32) -> bool {
    v.is_finite() && (0.0..=1.0).contains(&v)
}

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Vertex {
    pub position: [f32; 2],
    pub color: [f32; 4],
}

/// Tessellate each stroke once. Preserve source samples for later correction.
pub fn tessellate(stroke: &Stroke) -> Result<VertexBuffers<Vertex, u32>, String> {
    let mut mesh = VertexBuffers::new();
    let mut builder = Path::builder_with_attributes(1);
    let first = stroke.points.first().ok_or("Empty stroke")?;
    builder.begin(point(first.x, first.y), &[first.pressure.max(0.01)]);
    if stroke.points.len() == 1 {
        // A zero-length round-capped segment represents a tap.
        builder.line_to(point(first.x, first.y), &[first.pressure.max(0.01)]);
    }
    for p in stroke.points.iter().skip(1) {
        builder.line_to(point(p.x, p.y), &[p.pressure.max(0.01)]);
    }
    builder.end(false);
    StrokeTessellator::new()
        .tessellate_path(
            &builder.build(),
            &StrokeOptions::default()
                .with_line_width(stroke.width)
                .with_variable_line_width(0)
                .with_line_cap(LineCap::Round)
                .with_line_join(LineJoin::Round),
            &mut BuffersBuilder::new(&mut mesh, |v: StrokeVertex| Vertex {
                position: v.position().to_array(),
                color: stroke.color,
            }),
        )
        .map_err(|e| format!("{e:?}"))?;
    Ok(mesh)
}

#[cfg_attr(target_arch = "wasm32", wasm_bindgen::prelude::wasm_bindgen)]
pub struct Engine {
    document: Document,
    undo: Vec<Document>,
    redo: Vec<Document>,
}
#[cfg_attr(target_arch = "wasm32", wasm_bindgen::prelude::wasm_bindgen)]
impl Engine {
    #[cfg_attr(
        target_arch = "wasm32",
        wasm_bindgen::prelude::wasm_bindgen(constructor)
    )]
    pub fn new() -> Self {
        Self {
            document: Document {
                version: 1,
                layers: vec![],
            },
            undo: vec![],
            redo: vec![],
        }
    }
    pub fn export_json(&self) -> String {
        serde_json::to_string(&self.document).unwrap()
    }
    /// Validate before replacing state, so failed imports never damage the document.
    pub fn load_json(&mut self, json: &str) -> Result<(), String> {
        let next: Document = serde_json::from_str(json).map_err(|e| e.to_string())?;
        next.validate()?;
        self.commit(next);
        Ok(())
    }
    pub fn hit_test(&self, x: f32, y: f32, tolerance: f32) -> Option<String> {
        self.document.hit_test(x, y, tolerance)
    }
    pub fn delete_stroke(&mut self, id: &str) -> bool {
        let mut next = self.document.clone();
        for layer in &mut next.layers {
            if layer.locked {
                continue;
            }
            if let Some(i) = layer.strokes.iter().position(|s| s.id == id) {
                layer.strokes.remove(i);
                self.commit(next);
                return true;
            }
        }
        false
    }
    pub fn replace_stroke(&mut self, id: &str, json: &str) -> Result<(), String> {
        let replacement: Stroke = serde_json::from_str(json).map_err(|e| e.to_string())?;
        if replacement.id != id {
            return Err("Stroke ID must remain stable".into());
        }
        let mut next = self.document.clone();
        for layer in &mut next.layers {
            if layer.locked {
                continue;
            }
            if let Some(s) = layer.strokes.iter_mut().find(|s| s.id == id) {
                *s = replacement;
                next.validate()?;
                self.commit(next);
                return Ok(());
            }
        }
        Err("Stroke not found or layer locked".into())
    }
    pub fn undo(&mut self) -> bool {
        if let Some(previous) = self.undo.pop() {
            self.redo
                .push(std::mem::replace(&mut self.document, previous));
            true
        } else {
            false
        }
    }
    pub fn redo(&mut self) -> bool {
        if let Some(next) = self.redo.pop() {
            self.undo.push(std::mem::replace(&mut self.document, next));
            true
        } else {
            false
        }
    }
}
impl Default for Engine {
    fn default() -> Self {
        Self::new()
    }
}
impl Engine {
    fn commit(&mut self, next: Document) {
        if next == self.document {
            return;
        }
        if self.undo.len() == 64 {
            self.undo.remove(0);
        }
        self.undo.push(std::mem::replace(&mut self.document, next));
        self.redo.clear();
    }
}
