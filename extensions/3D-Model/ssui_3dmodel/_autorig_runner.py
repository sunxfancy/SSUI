"""Runs only in a model's isolated Python environment, never SSUI's process."""
import argparse
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(*args):
    # Upstream RigAnything splits paths on '/', including on Windows.
    values = [a.as_posix() if isinstance(a, Path) else str(a) for a in args]
    subprocess.run([sys.executable, *values], check=True)


def unirig(args):
    cache = args.output.parent / "npz"
    skeleton = args.output.with_name("skeleton.fbx")
    skin = args.output.with_name("skin.fbx")
    for source, target, task in (
        (args.input, skeleton, "quick_inference_skeleton_articulationxl_ar_256"),
        (skeleton, skin, "quick_inference_unirig_skin"),
    ):
        run("-m", "src.data.extract", "--config=configs/data/quick_inference.yaml",
            "--require_suffix=glb,fbx", "--force_override=true", "--num_runs=1", "--id=0",
            "--time=" + datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"),
            f"--faces_target_count={args.target_faces}", f"--input={source}", f"--output_dir={cache}")
        run(Path(__file__).with_name("_unirig_predict.py"), f"--task=configs/task/{task}.yaml", f"--seed={args.seed}",
            f"--input={source}", f"--output={target}", f"--npz_dir={cache}", "--data_name=raw_data.npz")
        if not target.is_file():
            raise RuntimeError(f"UniRig did not produce {target}")
    run(Path(__file__).with_name("_unirig_merge.py"), "--require_suffix=glb,fbx", "--num_runs=1", "--id=0",
        f"--source={skin}", f"--target={args.input}", f"--output={args.output}")


def riganything(args):
    work = args.output.parent / "riganything"
    work.mkdir()
    mesh = work / (args.input.stem + "_simplified.glb")
    # The upstream GLB preprocessing uses only bpy. Its script also imports
    # Open3D/PyMeshLab for the unused OBJ branch; avoid those unrelated binaries.
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.input))
    objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    faces = sum(len(obj.data.polygons) for obj in objects)
    if not faces:
        raise ValueError("Input GLB has no mesh faces")
    ratio = min(1.0, max(0.01, args.target_faces / faces))
    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
        modifier.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.ops.export_scene.gltf(filepath=str(mesh), export_format="GLB", export_materials="EXPORT", export_apply=False)
    if not mesh.is_file():
        raise RuntimeError(f"RigAnything did not produce {mesh}")
    # Upstream pins torch.manual_seed(777) inside inference.py.
    print("RigAnything uses its upstream fixed seed 777", flush=True)
    run("inference.py", "--config", "config.yaml", "--load", "ckpt/riganything_ckpt.pt",
        "-s", "inference", "true", "-s", "inference_out_dir", work, "--mesh_path", mesh)
    data = work / (mesh.stem + ".npz")
    if not data.is_file():
        raise RuntimeError(f"RigAnything did not produce {data}")
    run("inference_utils/vis_skel.py", "--data_path", data, "--save_path", work, "--mesh_path", mesh)
    shutil.copyfile(work / (mesh.stem + "_rig.glb"), args.output)


def mia(args):
    template = args.repo / "data/Mixamo/bones.fbx"
    if not template.is_file():
        raise FileNotFoundError(
            f"MIA skeleton template is missing: {template}. Authenticate with Hugging Face, "
            "obtain access to jasongzy/Mixamo, then rerun yarn install:rigging mia --cuda-native --download.")
    import app
    import bpy
    from argparse import Namespace
    from app_blender import main as export

    # The upstream stages return Gradio component mappings. Sentinel keys let
    # us use their inference API without creating or launching a Gradio server.
    for name in ("state", "output_joints_coarse", "output_normed_input", "output_sample",
                 "output_joints", "output_bw", "output_rest_lbs"):
        setattr(app, name, name)
    app.init_models()
    app.fix_random(args.seed)
    db = app.DB()
    app.prepare_input(str(args.input), db=db)
    app.preprocess(db)
    app.infer(False, db)
    app.vis(True, "LeftArm", False, db)
    export(Namespace(
        input_path=dict(mesh=db.mesh, gs=None, joints=db.joints, joints_tail=db.joints_tail,
                        bw=db.bw, pose=db.pose, bones_idx_dict=dict(app.bones_idx_dict_joints),
                        pose_ignore_list=[]),
        output_path=str(args.output.with_suffix(".fbx")), template_path=app.TEMPLATE_PATH,
        keep_raw=False, rest_path=None, pose_local=False, reset_to_rest=False,
        remove_fingers=False, animation_path=None, retarget=False, inplace=True,
    ))
    # Export Blender's live skinned scene directly; no external FBX converter.
    bpy.ops.export_scene.gltf(filepath=str(args.output), export_format="GLB", export_animations=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("unirig", "mia", "riganything"), required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-faces", type=int, default=8192)
    args = parser.parse_args()
    os.chdir(args.repo)
    sys.path.insert(0, str(args.repo))
    # Some upstream subprocess helpers call `python`; keep those in this venv.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    globals()[args.model](args)


if __name__ == "__main__":
    main()
