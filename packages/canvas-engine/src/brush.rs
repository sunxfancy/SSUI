use crate::Stroke;
use lyon_tessellation::{
    math::point, path::Path, BuffersBuilder, LineCap, LineJoin, StrokeOptions, StrokeTessellator,
    StrokeVertex, VertexBuffers,
};
use serde::{Deserialize, Serialize};
use std::hash::{Hash, Hasher};

#[derive(Clone, Copy, Debug, Default, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
#[repr(u32)]
pub enum Brush {
    #[default]
    Normal = 0,
    Pen = 1,
    Marker = 2,
    Watercolor = 3,
    Pencil = 4,
    Airbrush = 5,
    Texture = 6,
}
impl Brush {
    pub fn pressure(self, p: f32) -> f32 {
        match self {
            Self::Pen => p.max(0.01).powf(0.7),
            Self::Marker => 0.8 + 0.2 * p,
            Self::Pencil => 0.3 + 0.7 * p,
            _ => p.max(0.01),
        }
    }
}
#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
pub struct BrushVertex {
    pub position: [f32; 2],
    pub color: [u8; 4],
    pub center: [f32; 2],
    pub radius_feather: [f32; 2],
    pub brush_seed: u32,
}
pub fn mesh(
    stroke: &Stroke,
    brush: Brush,
    feather: f32,
    curve: Option<&crate::CurvePath>,
) -> Result<VertexBuffers<BrushVertex, u32>, String> {
    let mut path = Path::builder_with_attributes(1);
    let width = |p: f32| brush.pressure(p) + feather * 2. / stroke.width;
    if let Some(curve) = curve {
        let n = curve.nodes[0];
        path.begin(point(n[0], n[1]), &[width(curve.pressure_at(0.))]);
        if curve.nodes.len() == 1 {
            path.line_to(point(n[0], n[1]), &[width(curve.pressure_at(0.))]);
        }
        for pair in curve.nodes.windows(2) {
            let a = &pair[0];
            let b = &pair[1];
            for cuts in curve.cuts(a, b).windows(2) {
                let c = crate::CurvePath::slice(a, b, cuts[0], cuts[1]);
                path.cubic_bezier_to(
                    point(c[1][0], c[1][1]),
                    point(c[2][0], c[2][1]),
                    point(c[3][0], c[3][1]),
                    &[width(curve.pressure_at(a[6] + (b[6] - a[6]) * cuts[1]))],
                );
            }
        }
    } else {
        let first = stroke.points.first().ok_or("Empty stroke")?;
        path.begin(point(first.x, first.y), &[width(first.pressure)]);
        if stroke.points.len() == 1 {
            path.line_to(point(first.x, first.y), &[width(first.pressure)]);
        }
        for p in stroke.points.iter().skip(1) {
            path.line_to(point(p.x, p.y), &[width(p.pressure)]);
        }
    }
    path.end(false);
    let mut h = std::collections::hash_map::DefaultHasher::new();
    stroke.id.hash(&mut h);
    let seed = ((h.finish() as u32) & 0x00ffffff) << 8 | brush as u32;
    let mut buffers = VertexBuffers::new();
    StrokeTessellator::new()
        .tessellate_path(
            &path.build(),
            &StrokeOptions::default()
                .with_line_width(stroke.width)
                .with_variable_line_width(0)
                .with_line_join(LineJoin::Round)
                .with_line_cap(if matches!(brush, Brush::Marker) {
                    LineCap::Square
                } else {
                    LineCap::Round
                }),
            &mut BuffersBuilder::new(&mut buffers, |v: StrokeVertex| BrushVertex {
                position: v.position().to_array(),
                center: v.position_on_path().to_array(),
                color: stroke.color.map(|v| (v * 255.).round() as u8),
                radius_feather: [(v.line_width() / 2. - feather).max(0.001), feather],
                brush_seed: seed,
            }),
        )
        .map_err(|e| format!("{e:?}"))?;
    Ok(buffers)
}
