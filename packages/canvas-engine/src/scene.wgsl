struct Viewport { origin_zoom: vec4<f32>, size: vec4<f32> }
@group(0) @binding(0) var<uniform> viewport: Viewport;
struct StrokeOutput {
    @builtin(position) position: vec4<f32>, @location(0) color: vec4<f32>,
    @location(1) world:vec2<f32>, @location(2) center:vec2<f32>,
    @location(3) radius_feather:vec2<f32>, @location(4) @interpolate(flat) brush_seed:u32,
}
fn project(p: vec2<f32>) -> vec4<f32> {
    let pixel = (p-viewport.origin_zoom.xy)*viewport.origin_zoom.z;
    return vec4<f32>(pixel.x/viewport.size.x*2.-1.,1.-pixel.y/viewport.size.y*2.,0.,1.);
}
@vertex fn stroke_vertex(@location(0) p:vec2<f32>, @location(1) color:vec4<f32>,
    @location(2) center:vec2<f32>,@location(3) radius_feather:vec2<f32>,@location(4) brush_seed:u32)->StrokeOutput {
    var out:StrokeOutput; out.position=project(p);out.color=color;out.world=p;
    out.center=center;out.radius_feather=radius_feather;out.brush_seed=brush_seed;return out;
}
fn grain(p:vec2<f32>, seed:f32)->f32 {
    return fract(sin(dot(p,vec2<f32>(127.1,311.7))+seed)*43758.5453);
}
fn paper(p:vec2<f32>,seed:f32)->f32 {
    let cell=floor(p);let f=fract(p);let u=f*f*(3.-2.*f);
    return mix(mix(grain(cell,seed),grain(cell+vec2<f32>(1.,0.),seed),u.x),
        mix(grain(cell+vec2<f32>(0.,1.),seed),grain(cell+vec2<f32>(1.,1.),seed),u.x),u.y);
}
@fragment fn stroke_fragment(input:StrokeOutput)->@location(0) vec4<f32>{
    let kind=input.brush_seed & 255u;let seed=f32(input.brush_seed>>8u)*0.00001;
    let radius=max(input.radius_feather.x,0.001);let feather=input.radius_feather.y;
    let d=distance(input.world,input.center);let r=d/radius;
    var alpha=1.;
    if feather>0. {alpha*=1.-smoothstep(max(0.,radius-feather),radius+feather,d);}
    if kind==2u {alpha*=0.42;}
    if kind==3u {
        let pool=paper(input.world*0.07,seed);
        let fine=grain(floor(input.world*1.7),seed);
        alpha*=(0.12+pool*0.24+pow(min(r,1.),5.)*0.16)*(0.82+fine*0.18);
        alpha*=1.-smoothstep(0.82+pool*0.1,1.,r);
    }
    if kind==4u {
        let fine=grain(floor(input.world*2.1),seed);
        let fibres=grain(vec2<f32>(floor(input.world.x*0.7),floor(input.world.y*3.)),seed);
        alpha*=select(0.08,0.45+fine*0.4,fine>0.3+fibres*0.15);
        alpha*=1.-smoothstep(0.7+fine*0.22,1.,r);
    }
    if kind==5u {alpha*=exp(-r*r*3.)*0.22;}
    if kind==6u {alpha*=select(0.08,0.85,grain(floor(input.world*0.8),seed)>0.45);}
    return vec4<f32>(input.color.rgb,input.color.a*alpha);
}
struct ImageOutput { @builtin(position) position:vec4<f32>, @location(0) uv:vec2<f32> }
@group(1) @binding(0) var image_texture:texture_2d<f32>;
@group(1) @binding(1) var image_sampler:sampler;
@vertex fn image_vertex(@location(0) p:vec2<f32>,@location(1) uv:vec2<f32>)->ImageOutput{
    var out:ImageOutput;out.position=project(p);out.uv=uv;return out;
}
@fragment fn image_fragment(input:ImageOutput)->@location(0) vec4<f32>{return textureSample(image_texture,image_sampler,input.uv);}
// Separate entry point allows these bindings to share group 0 with the viewport.
@group(0) @binding(0) var layer_texture:texture_2d<f32>;
@group(0) @binding(1) var layer_sampler:sampler;
@group(0) @binding(2) var<uniform> opacity:vec4<f32>;
@vertex fn quad_vertex(@location(0) p:vec2<f32>,@location(1) uv:vec2<f32>)->ImageOutput{
    var out:ImageOutput;out.position=vec4<f32>(p,0.,1.);out.uv=uv;return out;
}
@fragment fn composite_fragment(input:ImageOutput)->@location(0) vec4<f32>{return textureSample(layer_texture,layer_sampler,input.uv)*opacity.x;}
