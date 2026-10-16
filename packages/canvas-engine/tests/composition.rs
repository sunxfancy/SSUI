use ssui_canvas_engine::{Scene, SceneRenderer};

#[test]
#[ignore = "Requires a GPU; run yarn test:gpu"]
fn gpu_layer_opacity_image_order_eraser_isolation_and_replay() {
    pollster::block_on(async {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: if cfg!(target_os = "windows") {
                wgpu::Backends::VULKAN
            } else {
                wgpu::Backends::PRIMARY
            },
            ..Default::default()
        });
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions::default())
            .await
            .expect("GPU adapter required");
        eprintln!("GPU pixel test: {:?}", adapter.get_info());
        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor::default())
            .await
            .unwrap();
        let mut renderer = SceneRenderer::new(&device, wgpu::TextureFormat::Rgba8Unorm);
        renderer
            .upload_image(&device, &queue, "red", 1, 1, &[255, 0, 0, 255])
            .unwrap();
        renderer
            .upload_image(&device, &queue, "blue", 1, 1, &[0, 0, 255, 255])
            .unwrap();
        let mut json = serde_json::json!({"layers":[
            {"id":"bottom","visible":true,"opacity":1,"objects":[
                {"kind":"image","id":"red-image","resource":"red","x":0,"y":0,"width":64,"height":64}]},
            {"id":"top","visible":true,"opacity":0.5,"objects":[
                {"kind":"image","id":"blue-image","resource":"blue","x":0,"y":0,"width":64,"height":64},
                {"kind":"stroke","stroke":{"id":"overlap","points":[{"x":0,"y":16,"pressure":1},{"x":64,"y":16,"pressure":1}],"width":12,"color":[0,0,1,1]}},
                {"kind":"stroke","erase":true,"stroke":{"id":"eraser","points":[{"x":0,"y":40,"pressure":1},{"x":64,"y":40,"pressure":1}],"width":12,"color":[0,0,0,1]}}
            ]}
        ]});
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: None,
            size: wgpu::Extent3d {
                width: 64,
                height: 64,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        for erased in [true, false] {
            if !erased {
                json["layers"][1]["objects"].as_array_mut().unwrap().pop();
            }
            let scene: Scene = serde_json::from_value(json.clone()).unwrap();
            renderer
                .render(
                    &device,
                    &queue,
                    &texture.create_view(&Default::default()),
                    &scene,
                    [64, 64],
                    [0., 0.],
                    1.,
                )
                .unwrap();
            let read = device.create_buffer(&wgpu::BufferDescriptor {
                label: None,
                size: 256 * 64,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            });
            let mut encoder = device.create_command_encoder(&Default::default());
            encoder.copy_texture_to_buffer(
                texture.as_image_copy(),
                wgpu::TexelCopyBufferInfo {
                    buffer: &read,
                    layout: wgpu::TexelCopyBufferLayout {
                        offset: 0,
                        bytes_per_row: Some(256),
                        rows_per_image: Some(64),
                    },
                },
                texture.size(),
            );
            queue.submit(Some(encoder.finish()));
            let (tx, rx) = std::sync::mpsc::channel();
            read.slice(..)
                .map_async(wgpu::MapMode::Read, move |r| tx.send(r).unwrap());
            device.poll(wgpu::PollType::Wait).unwrap();
            rx.recv().unwrap().unwrap();
            let bytes = read.slice(..).get_mapped_range();
            let pixel = |y: usize| bytes[(y * 256 + 32 * 4)..(y * 256 + 32 * 4 + 4)].to_vec();
            for y in [16, 28] {
                let p = pixel(y);
                assert!(
                    (p[0] as i32 - 127).abs() <= 2 && (p[2] as i32 - 128).abs() <= 2,
                    "layer opacity/overlap {p:?}"
                );
            }
            let p = pixel(40);
            if erased {
                assert_eq!(p, [255, 0, 0, 255], "eraser must reveal lower layer");
            } else {
                assert!(
                    (p[2] as i32 - 128).abs() <= 2,
                    "deleting eraser restores image: {p:?}"
                );
            }
        }
    });
}

#[test]
#[ignore = "Requires a GPU; run yarn test:gpu"]
fn sparse_tile_seams_replay_and_deletion_release_cache() {
    pollster::block_on(async {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: if cfg!(target_os = "windows") {
                wgpu::Backends::VULKAN
            } else {
                wgpu::Backends::PRIMARY
            },
            ..Default::default()
        });
        let adapter = instance.request_adapter(&Default::default()).await.unwrap();
        let (device, queue) = adapter.request_device(&Default::default()).await.unwrap();
        let mut renderer = SceneRenderer::new(&device, wgpu::TextureFormat::Rgba8Unorm);
        let mut json = serde_json::json!({"layers":[{"id":"ink","visible":true,"opacity":0.5,"objects":[
            {"kind":"stroke","stroke":{"id":"line","width":24,"color":[0,0,1,1],"points":[{"x":20,"y":250,"pressure":1},{"x":740,"y":270,"pressure":1}]}}
        ]}]});
        let output = device.create_texture(&wgpu::TextureDescriptor {
            label: None,
            size: wgpu::Extent3d {
                width: 768,
                height: 512,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let scene: Scene = serde_json::from_value(json.clone()).unwrap();
        renderer
            .render(
                &device,
                &queue,
                &output.create_view(&Default::default()),
                &scene,
                [768, 512],
                [0., 0.],
                1.,
            )
            .unwrap();
        let stats = renderer.stats();
        assert!(stats["tiles"].as_u64().unwrap() <= 6);
        assert_eq!(stats["images"], 0);
        let read = device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size: 3072 * 512,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut encoder = device.create_command_encoder(&Default::default());
        encoder.copy_texture_to_buffer(
            output.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &read,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(3072),
                    rows_per_image: Some(512),
                },
            },
            output.size(),
        );
        queue.submit(Some(encoder.finish()));
        let (tx, rx) = std::sync::mpsc::channel();
        read.slice(..)
            .map_async(wgpu::MapMode::Read, move |r| tx.send(r).unwrap());
        device.poll(wgpu::PollType::Wait).unwrap();
        rx.recv().unwrap().unwrap();
        {
            let bytes = read.slice(..).get_mapped_range();
            // Both sides of 256/512 seams retain the SAME premultiplied RGBA,
            // with layer opacity applied once and no duplicate gutter blend.
            for x in [254usize, 255, 256, 257, 510, 511, 512, 513] {
                let y = (250. + (x as f32 - 20.) / 720. * 20.) as usize;
                let p = &bytes[(y * 3072 + x * 4)..(y * 3072 + x * 4 + 4)];
                assert_eq!(&p[..2], &[0, 0]);
                assert!(
                    (p[2] as i32 - 128).abs() <= 1 && (p[3] as i32 - 128).abs() <= 1,
                    "seam {x}: {p:?}"
                );
            }
        }
        json["layers"][0]["objects"] = serde_json::json!([]);
        let empty: Scene = serde_json::from_value(json).unwrap();
        renderer
            .render(
                &device,
                &queue,
                &output.create_view(&Default::default()),
                &empty,
                [768, 512],
                [0., 0.],
                1.,
            )
            .unwrap();
        assert_eq!(renderer.stats()["gpu_payload_bytes"], 0);
    });
}
