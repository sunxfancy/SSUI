#include <torch/extension.h>
#include <ATen/mps/MPSStream.h>

// All buffers belong to PyTorch. Encode on its current stream so preceding
// sorts and subsequent gathers obey the same command ordering.
at::Tensor neighbors(at::Tensor coords, at::Tensor keys, at::Tensor order,
                     at::Tensor offsets, at::Tensor dims, at::Tensor strides) {
  for (const auto& t : {coords, keys, order, offsets, dims, strides}) {
    TORCH_CHECK(t.device().is_mps() && t.scalar_type() == at::kInt && t.is_contiguous(),
                "Metal neighbors expects contiguous MPS int32 tensors");
  }
  TORCH_CHECK(coords.dim() == 2 && coords.size(1) == 4 && offsets.dim() == 2 && offsets.size(1) == 4,
              "Expected Nx4 coordinates and Kx4 offsets");
  const uint32_t n = coords.size(0), k = offsets.size(0);
  TORCH_CHECK(n > 0 && uint64_t(n)*k < INT32_MAX && keys.numel() == n && order.numel() == n
              && dims.numel() == 4 && strides.numel() == 4, "Invalid neighbor dimensions");
  auto out = at::empty({k,n}, coords.options());
  static id<MTLComputePipelineState> pipeline = nil;
  auto stream = at::mps::getCurrentMPSStream();
  dispatch_sync(stream->queue(), ^{
    if (!pipeline) {
      NSString* source = @R"METAL(
#include <metal_stdlib>
using namespace metal;
kernel void neighbors(device const int4* coords [[buffer(0)]],
                      device const int* keys [[buffer(1)]],
                      device const int* order [[buffer(2)]],
                      device const int4* offsets [[buffer(3)]],
                      constant int4& dims [[buffer(4)]],
                      constant int4& strides [[buffer(5)]],
                      device int* output [[buffer(6)]],
                      constant uint& n [[buffer(7)]],
                      uint gid [[thread_position_in_grid]]) {
  int4 q = coords[gid % n] + offsets[gid / n];
  if (any(q < int4(0)) || any(q >= dims)) { output[gid] = -1; return; }
  int key = q.x*strides.x + q.y*strides.y + q.z*strides.z + q.w;
  uint lo = 0, hi = n;
  while (lo < hi) { uint mid = lo + (hi-lo)/2; if (keys[mid] < key) lo = mid+1; else hi = mid; }
  output[gid] = lo < n && keys[lo] == key ? order[lo] : -1;
}
)METAL";
      NSError* error = nil;
      auto device = MTLCreateSystemDefaultDevice();
      auto library = [device newLibraryWithSource:source options:nil error:&error];
      // Validated source is compiled once. Report compilation failure after
      // leaving the dispatch block rather than throwing across libdispatch.
      if (library) {
        auto function = [library newFunctionWithName:@"neighbors"];
        pipeline = [device newComputePipelineStateWithFunction:function error:&error];
        [function release]; [library release];
      }
      if (!pipeline) NSLog(@"TRELLIS Metal compilation: %@", error);
      [device release];
    }
    if (pipeline) {
      auto encoder = stream->commandEncoder();
      [encoder setComputePipelineState:pipeline];
      unsigned index = 0;
      for (const auto& t : {coords, keys, order, offsets, dims, strides, out}) {
        auto buffer = __builtin_bit_cast(id<MTLBuffer>, t.storage().data());
        [encoder setBuffer:buffer offset:t.storage_offset()*t.element_size() atIndex:index++];
      }
      [encoder setBytes:&n length:sizeof(n) atIndex:7];
      NSUInteger width = std::min<NSUInteger>(256, pipeline.maxTotalThreadsPerThreadgroup);
      [encoder dispatchThreads:MTLSizeMake(n*k,1,1) threadsPerThreadgroup:MTLSizeMake(width,1,1)];
    }
  });
  TORCH_CHECK(pipeline, "Could not compile TRELLIS Metal neighbor kernel; see Metal diagnostics");
  return out;
}
PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) { m.def("neighbors", &neighbors); }
