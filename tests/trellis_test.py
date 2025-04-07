import unittest
from PIL import Image
from tests.utils import should_run_slow_tests

class TrellisTest(unittest.TestCase):
    @unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
    def test_trellis(self):
        from trellis.pipelines import TrellisImageTo3DPipeline
        from trellis.utils import render_utils, postprocessing_utils
        # Load a pipeline from a model folder or a Hugging Face model hub.
        pipeline = TrellisImageTo3DPipeline.from_pretrained("JeffreyXiang/TRELLIS-image-large")
        pipeline.cuda()

        # Load an image
        image = Image.open("H:\\SSUI\\tests\\typical_building_building.png")

        # Run the pipeline
        outputs = pipeline.run(
            image,
            seed=1,
            # Optional parameters
            # sparse_structure_sampler_params={
            #     "steps": 12,
            #     "cfg_strength": 7.5,
            # },
            # slat_sampler_params={
            #     "steps": 12,
            #     "cfg_strength": 3,
            # },
        )
        # outputs is a dictionary containing generated 3D assets in different formats:
        # - outputs['gaussian']: a list of 3D Gaussians
        # - outputs['radiance_field']: a list of radiance fields
        # - outputs['mesh']: a list of meshes

        # Render the outputs
        # video = render_utils.render_video(outputs['gaussian'][0])['color']
        # imageio.mimsave("sample_gs.mp4", video, duration=25)
        # video = render_utils.render_video(outputs['radiance_field'][0])['color']
        # imageio.mimsave("sample_rf.mp4", video, duration=25)
        # video = render_utils.render_video(outputs['mesh'][0])['normal']
        # imageio.mimsave("sample_mesh.mp4", video, duration=25)

        # GLB files can be extracted from the outputs
        glb = postprocessing_utils.to_glb(
            outputs['gaussian'][0],
            outputs['mesh'][0],
            # Optional parameters
            simplify=0.95,          # Ratio of triangles to remove in the simplification process
            texture_size=1024,      # Size of the texture used for the GLB
        )
        glb.export("sample.glb")

        # Save Gaussians as PLY files
        outputs['gaussian'][0].save_ply("sample.ply")

        

