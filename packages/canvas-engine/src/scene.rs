//! Ordered object replay into isolated layer textures, followed by premultiplied composition.
use crate::tiles::{self, TileKey, GUTTER, TILE_EXTENT, TILE_SIZE};
use crate::{Brush, Stroke};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};
use wgpu::util::DeviceExt;

#[derive(Clone, Serialize, Deserialize)]
pub struct Scene {
    pub layers: Vec<SceneLayer>,
}
#[derive(Clone, Serialize, Deserialize)]
pub struct SceneLayer {
    pub id: String,
    pub visible: bool,
    pub opacity: f32,
    pub objects: Vec<SceneObject>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SceneObject {
    Stroke {
        stroke: Stroke,
        #[serde(default)]
        erase: bool,
        #[serde(default)]
        brush: Brush,
        #[serde(default)]
        feather: f32,
        #[serde(default)]
        curve: Option<crate::CurvePath>,
    },
    Image {
        id: String,
        resource: String,
        x: f32,
        y: f32,
        width: f32,
        height: f32,
        #[serde(default)]
        rotation: f32,
        #[serde(default)]
        erase: bool,
    },
}
impl SceneObject {
    pub(crate) fn id(&self) -> &str {
        match self {
            Self::Stroke { stroke, .. } => &stroke.id,
            Self::Image { id, .. } => id,
        }
    }
    pub(crate) fn erase(&self) -> bool {
        match self {
            Self::Stroke { erase, .. } | Self::Image { erase, .. } => *erase,
        }
    }
    pub(crate) fn fingerprint(&self) -> u64 {
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.id().hash(&mut h);
        self.erase().hash(&mut h);
        match self {
            Self::Stroke {
                stroke,
                brush,
                feather,
                curve,
                ..
            } => {
                0u8.hash(&mut h);
                brush.hash(&mut h);
                feather.to_bits().hash(&mut h);
                stroke.width.to_bits().hash(&mut h);
                for v in stroke.color {
                    v.to_bits().hash(&mut h);
                }
                for p in &stroke.points {
                    p.x.to_bits().hash(&mut h);
                    p.y.to_bits().hash(&mut h);
                    p.pressure.to_bits().hash(&mut h);
                }
                if let Some(curve) = curve {
                    for n in &curve.nodes {
                        for v in n {
                            v.to_bits().hash(&mut h);
                        }
                    }
                    for p in &curve.pressure {
                        for v in p {
                            v.to_bits().hash(&mut h);
                        }
                    }
                }
            }
            Self::Image {
                resource,
                x,
                y,
                width,
                height,
                rotation,
                ..
            } => {
                1u8.hash(&mut h);
                resource.hash(&mut h);
                for v in [x, y, width, height, rotation] {
                    v.to_bits().hash(&mut h);
                }
            }
        }
        h.finish()
    }
}
#[derive(Deserialize)]
pub struct SceneUpdate {
    layers: Vec<LayerUpdate>,
}
#[derive(Deserialize)]
struct LayerUpdate {
    id: String,
    visible: bool,
    opacity: f32,
    objects: Option<Vec<SceneObject>>,
}
impl SceneUpdate {
    /// Omitted object arrays reuse the previous immutable projection of that layer.
    pub fn apply(self, previous: &Scene) -> Result<Scene, String> {
        let mut layers = Vec::new();
        for layer in self.layers {
            let objects = match layer.objects {
                Some(objects) => objects,
                None => previous
                    .layers
                    .iter()
                    .find(|l| l.id == layer.id)
                    .ok_or("Unknown layer in incremental update")?
                    .objects
                    .clone(),
            };
            layers.push(SceneLayer {
                id: layer.id,
                visible: layer.visible,
                opacity: layer.opacity,
                objects,
            });
        }
        let scene = Scene { layers };
        scene.validate()?;
        Ok(scene)
    }
}
impl Scene {
    pub fn validate(&self) -> Result<(), String> {
        let mut ids = HashSet::new();
        for l in &self.layers {
            if l.id.is_empty()
                || !ids.insert(l.id.as_str())
                || !l.opacity.is_finite()
                || !(0.0..=1.0).contains(&l.opacity)
            {
                return Err("Invalid layer".into());
            }
            for object in &l.objects {
                if object.id().is_empty() || !ids.insert(object.id()) {
                    return Err("Duplicate object ID".into());
                }
                match object {
                    SceneObject::Stroke {
                        stroke,
                        feather,
                        curve,
                        ..
                    } => {
                        if let Some(curve) = curve {
                            stroke.validate_style()?;
                            curve.validate()?;
                            if !stroke.points.is_empty() {
                                return Err("Curve strokes must not duplicate dense samples".into());
                            }
                        } else {
                            stroke.validate()?;
                        }
                        if !feather.is_finite() || *feather < 0. {
                            return Err("Invalid feather".into());
                        }
                    }
                    SceneObject::Image {
                        resource,
                        x,
                        y,
                        width,
                        height,
                        rotation,
                        ..
                    } => {
                        if resource.is_empty()
                            || ![x, y, width, height, rotation]
                                .iter()
                                .all(|v| v.is_finite())
                            || *width <= 0.0
                            || *height <= 0.0
                        {
                            return Err("Invalid image geometry".into());
                        }
                    }
                }
            }
        }
        Ok(())
    }
}

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
struct TextureVertex {
    position: [f32; 2],
    uv: [f32; 2],
}
struct Mesh {
    key: u64,
    vertices: wgpu::Buffer,
    indices: wgpu::Buffer,
    count: u32,
    bytes: u64,
    index_format: wgpu::IndexFormat,
}
struct Image {
    _texture: wgpu::Texture,
    bind: wgpu::BindGroup,
}
struct LayerTarget {
    _texture: wgpu::Texture,
    view: wgpu::TextureView,
    bind: wgpu::BindGroup,
    _opacity: wgpu::Buffer,
    signature: Option<u64>,
    viewport: wgpu::Buffer,
    viewport_bind: wgpu::BindGroup,
}

pub struct SceneRenderer {
    stroke: wgpu::RenderPipeline,
    erase_stroke: wgpu::RenderPipeline,
    image: wgpu::RenderPipeline,
    erase_image: wgpu::RenderPipeline,
    composite: wgpu::RenderPipeline,
    viewport_layout: wgpu::BindGroupLayout,
    texture_layout: wgpu::BindGroupLayout,
    composite_layout: wgpu::BindGroupLayout,
    sampler: wgpu::Sampler,
    images: HashMap<String, Image>,
    meshes: HashMap<String, Mesh>,
    targets: HashMap<TileKey, LayerTarget>,
    msaa: Option<(wgpu::Texture, wgpu::TextureView)>,
    planner: tiles::TilePlanner,
}
const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;
impl SceneRenderer {
    pub fn new(device: &wgpu::Device, surface_format: wgpu::TextureFormat) -> Self {
        let uniform_entry = |binding| wgpu::BindGroupLayoutEntry {
            binding,
            visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
            ty: wgpu::BindingType::Buffer {
                ty: wgpu::BufferBindingType::Uniform,
                has_dynamic_offset: false,
                min_binding_size: None,
            },
            count: None,
        };
        let viewport_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("viewport"),
            entries: &[uniform_entry(0)],
        });
        let entries = [
            wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Texture {
                    sample_type: wgpu::TextureSampleType::Float { filterable: true },
                    view_dimension: wgpu::TextureViewDimension::D2,
                    multisampled: false,
                },
                count: None,
            },
            wgpu::BindGroupLayoutEntry {
                binding: 1,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                count: None,
            },
        ];
        let texture_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("image"),
            entries: &entries,
        });
        let composite_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("layer composition"),
            entries: &[entries[0], entries[1], uniform_entry(2)],
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("scene shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("scene.wgsl").into()),
        });
        let make = |label,
                    vertex_entry,
                    fragment_entry,
                    layouts: &[&wgpu::BindGroupLayout],
                    attributes: &[wgpu::VertexAttribute],
                    stride,
                    blend,
                    format| {
            let layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
                label: Some(label),
                bind_group_layouts: layouts,
                push_constant_ranges: &[],
            });
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some(label),
                layout: Some(&layout),
                vertex: wgpu::VertexState {
                    module: &shader,
                    entry_point: Some(vertex_entry),
                    compilation_options: Default::default(),
                    buffers: &[wgpu::VertexBufferLayout {
                        array_stride: stride,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes,
                    }],
                },
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: Some(fragment_entry),
                    compilation_options: Default::default(),
                    targets: &[Some(wgpu::ColorTargetState {
                        format,
                        blend: Some(blend),
                        write_mask: wgpu::ColorWrites::ALL,
                    })],
                }),
                primitive: wgpu::PrimitiveState::default(),
                depth_stencil: None,
                multisample: wgpu::MultisampleState {
                    count: if fragment_entry == "composite_fragment" {
                        1
                    } else {
                        4
                    },
                    ..Default::default()
                },
                multiview: None,
                cache: None,
            })
        };
        let erase_component = wgpu::BlendComponent {
            src_factor: wgpu::BlendFactor::Zero,
            dst_factor: wgpu::BlendFactor::OneMinusSrcAlpha,
            operation: wgpu::BlendOperation::Add,
        };
        let erase = wgpu::BlendState {
            color: erase_component,
            alpha: erase_component,
        };
        let stroke_attributes = wgpu::vertex_attr_array![0 => Float32x2, 1 => Unorm8x4, 2 => Float32x2, 3 => Float32x2, 4 => Uint32];
        let image_attributes = wgpu::vertex_attr_array![0 => Float32x2, 1 => Float32x2];
        let stroke = make(
            "ink",
            "stroke_vertex",
            "stroke_fragment",
            &[&viewport_layout],
            &stroke_attributes,
            32,
            wgpu::BlendState::ALPHA_BLENDING,
            FORMAT,
        );
        let erase_stroke = make(
            "erase ink",
            "stroke_vertex",
            "stroke_fragment",
            &[&viewport_layout],
            &stroke_attributes,
            32,
            erase,
            FORMAT,
        );
        let image = make(
            "image",
            "image_vertex",
            "image_fragment",
            &[&viewport_layout, &texture_layout],
            &image_attributes,
            16,
            wgpu::BlendState::ALPHA_BLENDING,
            FORMAT,
        );
        let erase_image = make(
            "erase image",
            "image_vertex",
            "image_fragment",
            &[&viewport_layout, &texture_layout],
            &image_attributes,
            16,
            erase,
            FORMAT,
        );
        let composite = make(
            "compose",
            "quad_vertex",
            "composite_fragment",
            &[&composite_layout],
            &image_attributes,
            16,
            wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING,
            surface_format,
        );
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });
        Self {
            stroke,
            erase_stroke,
            image,
            erase_image,
            composite,
            viewport_layout,
            texture_layout,
            composite_layout,
            sampler,
            images: HashMap::new(),
            meshes: HashMap::new(),
            targets: HashMap::new(),
            msaa: None,
            planner: tiles::TilePlanner::default(),
        }
    }
    pub fn upload_image(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        id: &str,
        width: u32,
        height: u32,
        rgba: &[u8],
    ) -> Result<(), String> {
        let limit = device.limits().max_texture_dimension_2d;
        if width == 0
            || height == 0
            || width > limit
            || height > limit
            || u64::from(width) * u64::from(height) * 4 != rgba.len() as u64
        {
            return Err("Invalid image buffer".into());
        }
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("source image"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: FORMAT,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        queue.write_texture(
            texture.as_image_copy(),
            rgba,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(width * 4),
                rows_per_image: Some(height),
            },
            texture.size(),
        );
        let bind = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.texture_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(
                        &texture.create_view(&Default::default()),
                    ),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.sampler),
                },
            ],
        });
        self.images.insert(
            id.into(),
            Image {
                _texture: texture,
                bind,
            },
        );
        for target in self.targets.values_mut() {
            target.signature = None;
        }
        Ok(())
    }
    /// Account for requested GPU payloads, not driver allocations or JS heap size.
    pub fn stats(&self) -> serde_json::Value {
        let tile_bytes = self.targets.len() as u64 * TILE_EXTENT as u64 * TILE_EXTENT as u64 * 4;
        let scratch_bytes = if self.msaa.is_some() {
            TILE_EXTENT as u64 * TILE_EXTENT as u64 * 16
        } else {
            0
        };
        let mesh_bytes: u64 = self.meshes.values().map(|m| m.bytes).sum();
        let uniform_bytes: u64 = self
            .targets
            .values()
            .map(|t| t._opacity.size() + t.viewport.size())
            .sum();
        let image_bytes: u64 = self
            .images
            .values()
            .map(|i| u64::from(i._texture.width()) * u64::from(i._texture.height()) * 4)
            .sum();
        serde_json::json!({"tile_size":TILE_SIZE,"tile_extent":TILE_EXTENT,"tiles":self.targets.len(),
            "meshes":self.meshes.len(),"images":self.images.len(),"tile_bytes":tile_bytes,
            "scratch_bytes":scratch_bytes,"mesh_bytes":mesh_bytes,"image_bytes":image_bytes,
            "uniform_bytes":uniform_bytes,
            "gpu_payload_bytes":tile_bytes+scratch_bytes+mesh_bytes+image_bytes+uniform_bytes})
    }
    fn create_tile(&self, device: &wgpu::Device) -> LayerTarget {
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("occupied layer tile"),
            size: wgpu::Extent3d {
                width: TILE_EXTENT,
                height: TILE_EXTENT,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: FORMAT,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        let view = texture.create_view(&Default::default());
        let opacity = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: None,
            contents: bytemuck::cast_slice(&[1f32, 0., 0., 0.]),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });
        let bind = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.composite_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.sampler),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: opacity.as_entire_binding(),
                },
            ],
        });
        let viewport = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("tile viewport"),
            contents: bytemuck::cast_slice(&[0f32; 8]),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });
        let viewport_bind = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.viewport_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: viewport.as_entire_binding(),
            }],
        });
        LayerTarget {
            _texture: texture,
            view,
            bind,
            _opacity: opacity,
            signature: None,
            viewport,
            viewport_bind,
        }
    }
    pub fn render(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        target: &wgpu::TextureView,
        scene: &Scene,
        size: [u32; 2],
        origin: [f32; 2],
        zoom: f32,
    ) -> Result<(), String> {
        scene.validate()?;
        if size.contains(&0)
            || size
                .iter()
                .any(|v| *v > device.limits().max_texture_dimension_2d)
            || !zoom.is_finite()
            || zoom <= 0.
            || !origin.iter().all(|v| v.is_finite())
        {
            return Err("Invalid viewport".into());
        }
        let plan = self.planner.plan(scene, size, origin, zoom);
        let active: HashSet<_> = plan.iter().map(|t| t.key.clone()).collect();
        self.targets.retain(|key, _| active.contains(key));
        let object_ids: HashSet<_> = plan
            .iter()
            .flat_map(|t| {
                t.objects
                    .iter()
                    .map(|i| scene.layers[t.layer].objects[*i].id())
            })
            .collect();
        // Offscreen/deleted meshes are disposable. Editable source samples stay in the scene.
        self.meshes.retain(|id, _| object_ids.contains(id.as_str()));
        let resources: HashSet<_> = scene
            .layers
            .iter()
            .flat_map(|l| &l.objects)
            .filter_map(|o| match o {
                SceneObject::Image { resource, .. } => Some(resource.as_str()),
                _ => None,
            })
            .collect();
        self.images.retain(|id, _| resources.contains(id.as_str()));
        for tile in &plan {
            for i in &tile.objects {
                if let SceneObject::Image { resource, .. } = &scene.layers[tile.layer].objects[*i] {
                    if !self.images.contains_key(resource) {
                        return Err("Image resource not uploaded".into());
                    }
                }
            }
        }
        if !plan.is_empty() && self.msaa.is_none() {
            let texture = device.create_texture(&wgpu::TextureDescriptor {
                label: Some("shared tile MSAA"),
                size: wgpu::Extent3d {
                    width: TILE_EXTENT,
                    height: TILE_EXTENT,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 4,
                dimension: wgpu::TextureDimension::D2,
                format: FORMAT,
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            });
            let view = texture.create_view(&Default::default());
            self.msaa = Some((texture, view));
        }
        if plan.is_empty() {
            self.msaa = None;
        }
        let mut dirty = HashSet::new();
        let mut checked = HashSet::new();
        for tile in &plan {
            if !self.targets.contains_key(&tile.key) {
                self.targets
                    .insert(tile.key.clone(), self.create_tile(device));
            }
            let target = &self.targets[&tile.key];
            let layer = &scene.layers[tile.layer];
            queue.write_buffer(
                &target._opacity,
                0,
                bytemuck::cast_slice(&[layer.opacity, 0., 0., 0.]),
            );
            if target.signature == Some(tile.signature) {
                continue;
            }
            dirty.insert(tile.key.clone());
            let left = tile.key.x as f32 * TILE_SIZE as f32 - GUTTER as f32;
            let top = tile.key.y as f32 * TILE_SIZE as f32 - GUTTER as f32;
            queue.write_buffer(
                &target.viewport,
                0,
                bytemuck::cast_slice(&[
                    origin[0] + left / zoom,
                    origin[1] + top / zoom,
                    zoom,
                    0.,
                    TILE_EXTENT as f32,
                    TILE_EXTENT as f32,
                    0.,
                    0.,
                ]),
            );
            for i in &tile.objects {
                let o = &layer.objects[*i];
                if !checked.insert(o.id()) {
                    continue;
                }
                let key = o.fingerprint();
                if self.meshes.get(o.id()).is_some_and(|m| m.key == key) {
                    continue;
                }
                let (vertices, indices) = match o {
                    SceneObject::Stroke {
                        stroke,
                        brush,
                        feather,
                        curve,
                        ..
                    } => {
                        let mesh = crate::brush::mesh(stroke, *brush, *feather, curve.as_ref())?;
                        (
                            bytemuck::cast_slice::<crate::brush::BrushVertex, u8>(&mesh.vertices)
                                .to_vec(),
                            mesh.indices,
                        )
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
                        let vertices: Vec<_> = [[0., 0.], [0., 1.], [1., 0.], [1., 1.]]
                            .into_iter()
                            .map(|uv| {
                                let px = uv[0] * width;
                                let py = uv[1] * height;
                                TextureVertex {
                                    position: [x + px * c - py * s, y + px * s + py * c],
                                    uv,
                                }
                            })
                            .collect();
                        (
                            bytemuck::cast_slice::<TextureVertex, u8>(&vertices).to_vec(),
                            vec![0, 1, 2, 2, 1, 3],
                        )
                    }
                };
                if indices.is_empty() {
                    self.meshes.remove(o.id());
                    continue;
                }
                let vb = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("cached brush mesh"),
                    contents: &vertices,
                    usage: wgpu::BufferUsages::VERTEX,
                });
                let (index_data, index_format) = if indices.iter().all(|i| *i <= u16::MAX as u32) {
                    let compact: Vec<_> = indices.iter().map(|i| *i as u16).collect();
                    (
                        bytemuck::cast_slice::<u16, u8>(&compact).to_vec(),
                        wgpu::IndexFormat::Uint16,
                    )
                } else {
                    (
                        bytemuck::cast_slice::<u32, u8>(&indices).to_vec(),
                        wgpu::IndexFormat::Uint32,
                    )
                };
                let ib = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: None,
                    contents: &index_data,
                    usage: wgpu::BufferUsages::INDEX,
                });
                let bytes = vb.size() + ib.size();
                self.meshes.insert(
                    o.id().into(),
                    Mesh {
                        key,
                        vertices: vb,
                        indices: ib,
                        count: indices.len() as u32,
                        bytes,
                        index_format,
                    },
                );
            }
        }
        let mut encoder = device.create_command_encoder(&Default::default());
        for tile in &plan {
            if !dirty.contains(&tile.key) {
                continue;
            }
            let target = &self.targets[&tile.key];
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("replay occupied tile"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &self.msaa.as_ref().unwrap().1,
                    resolve_target: Some(&target.view),
                    depth_slice: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT),
                        store: wgpu::StoreOp::Discard,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_bind_group(0, &target.viewport_bind, &[]);
            for i in &tile.objects {
                let o = &scene.layers[tile.layer].objects[*i];
                let Some(mesh) = self.meshes.get(o.id()) else {
                    continue;
                };
                match o {
                    SceneObject::Stroke { .. } => pass.set_pipeline(if o.erase() {
                        &self.erase_stroke
                    } else {
                        &self.stroke
                    }),
                    SceneObject::Image { resource, .. } => {
                        pass.set_pipeline(if o.erase() {
                            &self.erase_image
                        } else {
                            &self.image
                        });
                        pass.set_bind_group(1, &self.images[resource].bind, &[]);
                    }
                }
                pass.set_vertex_buffer(0, mesh.vertices.slice(..));
                pass.set_index_buffer(mesh.indices.slice(..), mesh.index_format);
                pass.draw_indexed(0..mesh.count, 0, 0..1);
            }
        }
        let mut quads = Vec::with_capacity(plan.len() * 6);
        let uv0 = GUTTER as f32 / TILE_EXTENT as f32;
        let uv1 = (GUTTER + TILE_SIZE) as f32 / TILE_EXTENT as f32;
        for tile in &plan {
            let x = tile.key.x as f32 * TILE_SIZE as f32;
            let y = tile.key.y as f32 * TILE_SIZE as f32;
            let p = |dx: f32, dy: f32| {
                [
                    (x + dx) / size[0] as f32 * 2. - 1.,
                    1. - (y + dy) / size[1] as f32 * 2.,
                ]
            };
            quads.extend([
                TextureVertex {
                    position: p(0., 0.),
                    uv: [uv0, uv0],
                },
                TextureVertex {
                    position: p(0., TILE_SIZE as f32),
                    uv: [uv0, uv1],
                },
                TextureVertex {
                    position: p(TILE_SIZE as f32, 0.),
                    uv: [uv1, uv0],
                },
                TextureVertex {
                    position: p(TILE_SIZE as f32, 0.),
                    uv: [uv1, uv0],
                },
                TextureVertex {
                    position: p(0., TILE_SIZE as f32),
                    uv: [uv0, uv1],
                },
                TextureVertex {
                    position: p(TILE_SIZE as f32, TILE_SIZE as f32),
                    uv: [uv1, uv1],
                },
            ]);
        }
        let quad_buffer = if quads.is_empty() {
            None
        } else {
            Some(
                device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("tile quads"),
                    contents: bytemuck::cast_slice(&quads),
                    usage: wgpu::BufferUsages::VERTEX,
                }),
            )
        };
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("compose sparse layers"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: target,
                    resolve_target: None,
                    depth_slice: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&self.composite);
            if let Some(buffer) = &quad_buffer {
                pass.set_vertex_buffer(0, buffer.slice(..));
                for (i, tile) in plan.iter().enumerate() {
                    pass.set_bind_group(0, &self.targets[&tile.key].bind, &[]);
                    pass.draw(i as u32 * 6..i as u32 * 6 + 6, 0..1);
                }
            }
        }
        queue.submit(Some(encoder.finish()));
        for tile in &plan {
            if dirty.contains(&tile.key) {
                self.targets.get_mut(&tile.key).unwrap().signature = Some(tile.signature);
            }
        }
        Ok(())
    }
}
