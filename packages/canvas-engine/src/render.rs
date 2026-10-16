use crate::{tessellate, Document, Vertex};
use wgpu::util::DeviceExt;

/// Portable GPU pipeline. The host owns the surface, scheduling and layer compositor.
pub struct Renderer {
    pipeline: wgpu::RenderPipeline,
}
impl Renderer {
    pub fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("canvas strokes"),
            source: wgpu::ShaderSource::Wgsl(include_str!("stroke.wgsl").into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("canvas strokes"),
            layout: None,
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                compilation_options: Default::default(),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: std::mem::size_of::<Vertex>() as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &wgpu::vertex_attr_array![0 => Float32x2, 1 => Float32x4],
                }],
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        Self { pipeline }
    }

    /// Render ONE layer into a transparent texture. Apply layer opacity only when
    /// compositing this texture, otherwise overlapping strokes get incorrect opacity.
    pub fn render_layer(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        target: &wgpu::TextureView,
        document: &Document,
        layer_id: &str,
        size: [u32; 2],
        origin: [f32; 2],
        zoom: f32,
    ) -> Result<(), String> {
        document.validate()?;
        if size.contains(&0)
            || !zoom.is_finite()
            || zoom <= 0.0
            || !origin.iter().all(|v| v.is_finite())
        {
            return Err("Invalid viewport".into());
        }
        let layer = document
            .layers
            .iter()
            .find(|l| l.id == layer_id)
            .ok_or("Missing layer")?;
        let mut vertices = Vec::new();
        let mut indices = Vec::new();
        if layer.visible {
            for stroke in &layer.strokes {
                let mesh = tessellate(stroke)?;
                let base = vertices.len() as u32;
                vertices.extend(mesh.vertices.into_iter().map(|mut v| {
                    v.position = [
                        2.0 * (v.position[0] - origin[0]) * zoom / size[0] as f32 - 1.0,
                        1.0 - 2.0 * (v.position[1] - origin[1]) * zoom / size[1] as f32,
                    ];
                    v
                }));
                indices.extend(mesh.indices.into_iter().map(|i| i + base));
            }
        }
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor::default());
        let buffers = if indices.is_empty() {
            None
        } else {
            Some((
                device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("stroke vertices"),
                    contents: bytemuck::cast_slice(&vertices),
                    usage: wgpu::BufferUsages::VERTEX,
                }),
                device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("stroke indices"),
                    contents: bytemuck::cast_slice(&indices),
                    usage: wgpu::BufferUsages::INDEX,
                }),
            ))
        };
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("canvas layer"),
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
            if let Some((vertex, index)) = &buffers {
                pass.set_pipeline(&self.pipeline);
                pass.set_vertex_buffer(0, vertex.slice(..));
                pass.set_index_buffer(index.slice(..), wgpu::IndexFormat::Uint32);
                pass.draw_indexed(0..indices.len() as u32, 0, 0..1);
            }
        }
        queue.submit(Some(encoder.finish()));
        Ok(())
    }
}

#[cfg(target_arch = "wasm32")]
mod web {
    use super::*;
    use std::sync::{Arc, Mutex};
    use wasm_bindgen::prelude::*;
    #[wasm_bindgen]
    pub struct CanvasRenderer {
        surface: wgpu::Surface<'static>,
        device: wgpu::Device,
        queue: wgpu::Queue,
        config: wgpu::SurfaceConfiguration,
        renderer: Renderer,
        scene_renderer: crate::SceneRenderer,
        scene: crate::Scene,
        failure: Arc<Mutex<Option<String>>>,
    }
    #[wasm_bindgen]
    impl CanvasRenderer {
        /// Create a browser renderer with isolated layers and transparent presentation.
        pub async fn create(canvas: web_sys::HtmlCanvasElement) -> Result<CanvasRenderer, JsValue> {
            let instance = wgpu::Instance::default();
            let surface = instance
                .create_surface(wgpu::SurfaceTarget::Canvas(canvas.clone()))
                .map_err(|e| JsValue::from_str(&e.to_string()))?;
            let adapter = instance
                .request_adapter(&wgpu::RequestAdapterOptions {
                    compatible_surface: Some(&surface),
                    ..Default::default()
                })
                .await
                .map_err(|e| JsValue::from_str(&e.to_string()))?;
            let (device, queue) = adapter
                .request_device(&wgpu::DeviceDescriptor {
                    label: Some("SSUI canvas"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::default(),
                    ..Default::default()
                })
                .await
                .map_err(|e| JsValue::from_str(&e.to_string()))?;
            let failure = Arc::new(Mutex::new(None));
            let errors = failure.clone();
            device.on_uncaptured_error(Box::new(move |error| {
                *errors.lock().unwrap() = Some(format!("{error}"));
            }));
            let lost = failure.clone();
            device.set_device_lost_callback(move |reason, message| {
                *lost.lock().unwrap() = Some(format!("GPU device lost: {reason:?}: {message}"));
            });
            if canvas.width() > device.limits().max_texture_dimension_2d
                || canvas.height() > device.limits().max_texture_dimension_2d
            {
                return Err(JsValue::from_str("Canvas exceeds GPU texture limit"));
            }
            let mut config = surface
                .get_default_config(&adapter, canvas.width().max(1), canvas.height().max(1))
                .ok_or_else(|| JsValue::from_str("Unsupported canvas surface"))?;
            // WebGPU guarantees premultiplied canvas alpha. The web backend reports
            // only Opaque in capabilities even though configure supports both modes.
            config.alpha_mode = wgpu::CompositeAlphaMode::PreMultiplied;
            surface.configure(&device, &config);
            device.push_error_scope(wgpu::ErrorFilter::Validation);
            let renderer = Renderer::new(&device, config.format);
            let scene_renderer = crate::SceneRenderer::new(&device, config.format);
            if let Some(error) = device.pop_error_scope().await {
                return Err(JsValue::from_str(&error.to_string()));
            }
            Ok(Self {
                surface,
                device,
                queue,
                config,
                renderer,
                scene_renderer,
                scene: crate::Scene { layers: vec![] },
                failure,
            })
        }
        pub fn resize(&mut self, width: u32, height: u32) -> Result<(), JsValue> {
            if width == 0
                || height == 0
                || width > self.device.limits().max_texture_dimension_2d
                || height > self.device.limits().max_texture_dimension_2d
            {
                return Err(JsValue::from_str("Invalid canvas size"));
            }
            self.config.width = width;
            self.config.height = height;
            self.surface.configure(&self.device, &self.config);
            Ok(())
        }
        pub fn error(&self) -> Option<String> {
            self.failure.lock().unwrap().clone()
        }
        pub fn stats_json(&self) -> String {
            self.scene_renderer.stats().to_string()
        }
        pub fn render_layer(
            &self,
            engine: &crate::Engine,
            layer_id: &str,
            x: f32,
            y: f32,
            zoom: f32,
        ) -> Result<(), JsValue> {
            let frame = self
                .surface
                .get_current_texture()
                .map_err(|e| JsValue::from_str(&e.to_string()))?;
            let view = frame.texture.create_view(&Default::default());
            self.renderer
                .render_layer(
                    &self.device,
                    &self.queue,
                    &view,
                    &engine.document,
                    layer_id,
                    [self.config.width, self.config.height],
                    [x, y],
                    zoom,
                )
                .map_err(|e| JsValue::from_str(&e))?;
            frame.present();
            Ok(())
        }
        pub fn upload_image(
            &mut self,
            id: &str,
            width: u32,
            height: u32,
            rgba: &[u8],
        ) -> Result<(), JsValue> {
            self.scene_renderer
                .upload_image(&self.device, &self.queue, id, width, height, rgba)
                .map_err(|e| JsValue::from_str(&e))
        }
        pub fn render_scene(
            &mut self,
            json: &str,
            x: f32,
            y: f32,
            zoom: f32,
        ) -> Result<(), JsValue> {
            if let Some(error) = self.error() {
                return Err(JsValue::from_str(&error));
            }
            let scene: crate::Scene =
                serde_json::from_str(json).map_err(|e| JsValue::from_str(&e.to_string()))?;
            // Retry a recoverable surface loss once. Device loss is handled by the host fallback.
            let frame = match self.surface.get_current_texture() {
                Ok(frame) => frame,
                Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                    self.surface.configure(&self.device, &self.config);
                    self.surface
                        .get_current_texture()
                        .map_err(|e| JsValue::from_str(&e.to_string()))?
                }
                Err(e) => return Err(JsValue::from_str(&e.to_string())),
            };
            self.scene_renderer
                .render(
                    &self.device,
                    &self.queue,
                    &frame.texture.create_view(&Default::default()),
                    &scene,
                    [self.config.width, self.config.height],
                    [x, y],
                    zoom,
                )
                .map_err(|e| JsValue::from_str(&e))?;
            frame.present();
            Ok(())
        }
        pub fn render_scene_update(
            &mut self,
            json: &str,
            x: f32,
            y: f32,
            zoom: f32,
        ) -> Result<(), JsValue> {
            if let Some(error) = self.error() {
                return Err(JsValue::from_str(&error));
            }
            let update: crate::SceneUpdate =
                serde_json::from_str(json).map_err(|e| JsValue::from_str(&e.to_string()))?;
            let scene = update
                .apply(&self.scene)
                .map_err(|e| JsValue::from_str(&e))?;
            let frame = match self.surface.get_current_texture() {
                Ok(frame) => frame,
                Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                    self.surface.configure(&self.device, &self.config);
                    self.surface
                        .get_current_texture()
                        .map_err(|e| JsValue::from_str(&e.to_string()))?
                }
                Err(e) => return Err(JsValue::from_str(&e.to_string())),
            };
            self.scene_renderer
                .render(
                    &self.device,
                    &self.queue,
                    &frame.texture.create_view(&Default::default()),
                    &scene,
                    [self.config.width, self.config.height],
                    [x, y],
                    zoom,
                )
                .map_err(|e| JsValue::from_str(&e))?;
            self.scene = scene;
            frame.present();
            Ok(())
        }
        /// Includes GPU completion; useful for bounded latency measurements.
        pub async fn wait_idle(&self) -> Result<(), JsValue> {
            let (sender, receiver) = futures_channel::oneshot::channel();
            self.queue.on_submitted_work_done(move || {
                let _ = sender.send(());
            });
            receiver
                .await
                .map_err(|e| JsValue::from_str(&e.to_string()))
        }
    }
}
