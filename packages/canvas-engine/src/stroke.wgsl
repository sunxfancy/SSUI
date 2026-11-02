struct Output {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec4<f32>,
};
@vertex fn vs_main(@location(0) position: vec2<f32>, @location(1) color: vec4<f32>) -> Output {
    var output: Output;
    output.position = vec4<f32>(position, 0.0, 1.0);
    output.color = color;
    return output;
}
@fragment fn fs_main(input: Output) -> @location(0) vec4<f32> {
    return input.color;
}
