import torch
from pytorch3d.renderer.cameras import look_at_view_transform, OrthographicCameras, CamerasBase
from pytorch3d.renderer import (
    RasterizationSettings,
    TexturesVertex,
    FoVPerspectiveCameras,
    FoVOrthographicCameras,
)
from pytorch3d.structures import Meshes
from PIL import Image
from typing import List
from refine.render import _warmup
import pymeshlab as ml
from pymeshlab import Percentage
import nvdiffrast.torch as dr
import numpy as np


def _translation(x, y, z, device):
    return torch.tensor([[1., 0, 0, x],
                    [0, 1, 0, y],
                    [0, 0, 1, z],
                    [0, 0, 0, 1]],device=device) #4,4

def _projection(r, device, l=None, t=None, b=None, n=1.0, f=50.0, flip_y=True):
    """
        see https://blog.csdn.net/wodownload2/article/details/85069240/
    """
    if l is None:
        l = -r
    if t is None:
        t = r
    if b is None:
        b = -t
    p = torch.zeros([4,4],device=device)
    p[0,0] = 2*n/(r-l)
    p[0,2] = (r+l)/(r-l)
    p[1,1] = 2*n/(t-b) * (-1 if flip_y else 1)
    p[1,2] = (t+b)/(t-b)
    p[2,2] = -(f+n)/(f-n)
    p[2,3] = -(2*f*n)/(f-n)
    p[3,2] = -1
    return p #4,4

def _orthographic(r, device, l=None, t=None, b=None, n=1.0, f=50.0, flip_y=True):
    if l is None:
        l = -r
    if t is None:
        t = r
    if b is None:
        b = -t
    o = torch.zeros([4,4],device=device)
    o[0,0] = 2/(r-l)
    o[0,3] = -(r+l)/(r-l)
    o[1,1] = 2/(t-b) * (-1 if flip_y else 1)
    o[1,3] = -(t+b)/(t-b)
    o[2,2] = -2/(f-n)
    o[2,3] = -(f+n)/(f-n)
    o[3,3] = 1
    return o #4,4

def make_star_cameras(az_count,pol_count,distance:float=10.,r=None,image_size=[512,512],device='cuda'):
    if r is None:
        r = 1/distance
    A = az_count
    P = pol_count
    C = A * P

    phi = torch.arange(0,A) * (2*torch.pi/A)
    phi_rot = torch.eye(3,device=device)[None,None].expand(A,1,3,3).clone()
    phi_rot[:,0,2,2] = phi.cos()
    phi_rot[:,0,2,0] = -phi.sin()
    phi_rot[:,0,0,2] = phi.sin()
    phi_rot[:,0,0,0] = phi.cos()
    
    theta = torch.arange(1,P+1) * (torch.pi/(P+1)) - torch.pi/2
    theta_rot = torch.eye(3,device=device)[None,None].expand(1,P,3,3).clone()
    theta_rot[0,:,1,1] = theta.cos()
    theta_rot[0,:,1,2] = -theta.sin()
    theta_rot[0,:,2,1] = theta.sin()
    theta_rot[0,:,2,2] = theta.cos()

    mv = torch.empty((C,4,4), device=device)
    mv[:] = torch.eye(4, device=device)
    mv[:,:3,:3] = (theta_rot @ phi_rot).reshape(C,3,3)
    mv = _translation(0, 0, -distance, device) @ mv

    return mv, _projection(r,device)


def make_star_cameras_orthographic(az_count,pol_count,distance:float=10.,r=None,image_size=[512,512],device='cuda'):
    mv, _ = make_star_cameras(az_count,pol_count,distance,r,image_size,device)
    if r is None:
        r = 1
    return mv, _orthographic(r,device)


def get_camera(world_to_cam, fov_in_degrees=60, focal_length=1 / (2**0.5), cam_type='fov'):
    # pytorch3d expects transforms as row-vectors, so flip rotation: https://github.com/facebookresearch/pytorch3d/issues/1183
    R = world_to_cam[:3, :3].t()[None, ...]
    T = world_to_cam[:3, 3][None, ...]
    if cam_type == 'fov':
        camera = FoVPerspectiveCameras(device=world_to_cam.device, R=R, T=T, fov=fov_in_degrees, degrees=True)
    else:
        focal_length = 1 / focal_length
        camera = FoVOrthographicCameras(device=world_to_cam.device, R=R, T=T, min_x=-focal_length, max_x=focal_length, min_y=-focal_length, max_y=focal_length)
    return camera


def get_cameras_list(azim_list, device, focal=2/1.35, dist=1.1):
    ret = []
    for azim in azim_list:
        R, T = look_at_view_transform(dist, 0, azim)
        w2c = torch.cat([R[0].T, T[0, :, None]], dim=1)
        cameras: OrthographicCameras = get_camera(w2c, focal_length=focal, cam_type='orthogonal').to(device)
        ret.append(cameras)
    return ret


def to_py3d_mesh(vertices, faces, normals=None):
    from pytorch3d.structures import Meshes
    from pytorch3d.renderer.mesh.textures import TexturesVertex
    mesh = Meshes(verts=[vertices], faces=[faces], textures=None)
    if normals is None:
        normals = mesh.verts_normals_packed()
    # set normals as vertext colors
    mesh.textures = TexturesVertex(verts_features=[normals / 2 + 0.5])
    return mesh


def from_py3d_mesh(mesh):
    return mesh.verts_list()[0], mesh.faces_list()[0], mesh.textures.verts_features_packed()


class Pix2FacesRenderer:
    def __init__(self, device="cuda"):
        self._glctx = dr.RasterizeCudaContext(device=device)
        self.device = device
        _warmup(self._glctx, device)

    def transform_vertices(self, meshes: Meshes, cameras: CamerasBase):
        vertices = cameras.transform_points_ndc(meshes.verts_padded())

        perspective_correct = cameras.is_perspective()
        znear = cameras.get_znear()
        if isinstance(znear, torch.Tensor):
            znear = znear.min().item()
        z_clip = None if not perspective_correct or znear is None else znear / 2

        if z_clip:
            vertices = vertices[vertices[..., 2] >= cameras.get_znear()][None]    # clip
        vertices = vertices * torch.tensor([-1, -1, 1]).to(vertices)
        vertices = torch.cat([vertices, torch.ones_like(vertices[..., :1])], dim=-1).to(torch.float32)
        return vertices

    def render_pix2faces_nvdiff(self, meshes: Meshes, cameras: CamerasBase, H=512, W=512):
        meshes = meshes.to(self.device)
        cameras = cameras.to(self.device)
        vertices = self.transform_vertices(meshes, cameras)
        faces = meshes.faces_packed().to(torch.int32)
        rast_out,_ = dr.rasterize(self._glctx, vertices, faces, resolution=(H, W), grad_db=False) #C,H,W,4
        pix_to_face = rast_out[..., -1].to(torch.int32) - 1
        return pix_to_face

pix2faces_renderer = Pix2FacesRenderer()

def get_visible_faces(meshes: Meshes, cameras: CamerasBase, resolution=1024):
    # pix_to_face = render_pix2faces_py3d(meshes, cameras, H=resolution, W=resolution)['pix_to_face']
    pix_to_face = pix2faces_renderer.render_pix2faces_nvdiff(meshes, cameras, H=resolution, W=resolution)

    unique_faces = torch.unique(pix_to_face.flatten())
    unique_faces = unique_faces[unique_faces != -1]
    return unique_faces


def project_color(meshes: Meshes, cameras: CamerasBase, pil_image: Image.Image, use_alpha=True, eps=0.05, resolution=1024, device="cuda") -> dict:
    """
    Projects color from a given image onto a 3D mesh.

    Args:
        meshes (pytorch3d.structures.Meshes): The 3D mesh object.
        cameras (pytorch3d.renderer.cameras.CamerasBase): The camera object.
        pil_image (PIL.Image.Image): The input image.
        use_alpha (bool, optional): Whether to use the alpha channel of the image. Defaults to True.
        eps (float, optional): The threshold for selecting visible faces. Defaults to 0.05.
        resolution (int, optional): The resolution of the projection. Defaults to 1024.
        device (str, optional): The device to use for computation. Defaults to "cuda".
        debug (bool, optional): Whether to save debug images. Defaults to False.

    Returns:
        dict: A dictionary containing the following keys:
            - "new_texture" (TexturesVertex): The updated texture with interpolated colors.
            - "valid_verts" (Tensor of [M,3]): The indices of the vertices being projected.
            - "valid_colors" (Tensor of [M,3]): The interpolated colors for the valid vertices.
    """
    meshes = meshes.to(device)
    cameras = cameras.to(device)
    image = torch.from_numpy(np.array(pil_image.convert("RGBA")) / 255.).permute((2, 0, 1)).float().to(device)     # in CHW format of [0, 1.]
    unique_faces = get_visible_faces(meshes, cameras, resolution=resolution)

    # visible faces
    faces_normals = meshes.faces_normals_packed()[unique_faces]
    faces_normals = faces_normals / faces_normals.norm(dim=1, keepdim=True)
    world_points = cameras.unproject_points(torch.tensor([[[0., 0., 0.1], [0., 0., 0.2]]]).to(device))[0]
    view_direction = world_points[1] - world_points[0]
    view_direction = view_direction / view_direction.norm(dim=0, keepdim=True)

    # find invalid faces
    cos_angles = (faces_normals * view_direction).sum(dim=1)
    assert cos_angles.mean() < 0, f"The view direction is not correct. cos_angles.mean()={cos_angles.mean()}"
    selected_faces = unique_faces[cos_angles < -eps]

    # find verts
    faces = meshes.faces_packed()[selected_faces]   # [N, 3]
    verts = torch.unique(faces.flatten())   # [N, 1]
    verts_coordinates = meshes.verts_packed()[verts]   # [N, 3]

    # compute color
    pt_tensor = cameras.transform_points(verts_coordinates)[..., :2] # NDC space points
    valid = ~((pt_tensor.isnan()|(pt_tensor<-1)|(1<pt_tensor)).any(dim=1))  # checked, correct
    valid_pt = pt_tensor[valid, :]
    valid_idx = verts[valid]
    valid_color = torch.nn.functional.grid_sample(image[None].flip((-1, -2)), valid_pt[None, :, None, :], align_corners=False, padding_mode="reflection", mode="bilinear")[0, :, :, 0].T.clamp(0, 1)   # [N, 4], note that bicubic may give invalid value
    alpha, valid_color = valid_color[:, 3:], valid_color[:, :3]
    if not use_alpha:
        alpha = torch.ones_like(alpha)

    # modify color
    old_colors = meshes.textures.verts_features_packed()
    old_colors[valid_idx] = valid_color * alpha + old_colors[valid_idx] * (1 - alpha)
    new_texture = TexturesVertex(verts_features=[old_colors])
    
    valid_verts_normals = meshes.verts_normals_packed()[valid_idx]
    valid_verts_normals = valid_verts_normals / valid_verts_normals.norm(dim=1, keepdim=True).clamp_min(0.001)
    cos_angles = (valid_verts_normals * view_direction).sum(dim=1)
    return {
        "new_texture": new_texture,
        "valid_verts": valid_idx,
        "valid_colors": valid_color,
        "valid_alpha": alpha,
        "cos_angles": cos_angles,
    }

def complete_unseen_vertex_color(meshes: Meshes, valid_index: torch.Tensor) -> dict:
    """
    meshes: the mesh with vertex color to be completed.
    valid_index: the index of the valid vertices, where valid means colors are fixed. [V, 1]
    """
    valid_index = valid_index.to(meshes.device)
    colors = meshes.textures.verts_features_packed()    # [V, 3]
    V = colors.shape[0]
    
    invalid_index = torch.ones_like(colors[:, 0]).bool()    # [V]
    invalid_index[valid_index] = False
    invalid_index = torch.arange(V).to(meshes.device)[invalid_index]
    
    L = meshes.laplacian_packed()
    E = torch.sparse_coo_tensor(torch.tensor([list(range(V))] * 2), torch.ones((V,)), size=(V, V)).to(meshes.device)
    L = L + E
    # import pdb; pdb.set_trace()
    # E = torch.eye(V, layout=torch.sparse_coo, device=meshes.device)
    # L = L + E
    colored_count = torch.ones_like(colors[:, 0])   # [V]
    colored_count[invalid_index] = 0
    L_invalid = torch.index_select(L, 0, invalid_index)    # sparse [IV, V]
    
    total_colored = colored_count.sum()
    coloring_round = 0
    stage = "uncolored"
    from tqdm import tqdm
    pbar = tqdm(miniters=100)
    while stage == "uncolored" or coloring_round > 0:
        new_color = torch.matmul(L_invalid, colors * colored_count[:, None])    # [IV, 3]
        new_count = torch.matmul(L_invalid, colored_count)[:, None]             # [IV, 1]
        colors[invalid_index] = torch.where(new_count > 0, new_color / new_count, colors[invalid_index])
        colored_count[invalid_index] = (new_count[:, 0] > 0).float()
        
        new_total_colored = colored_count.sum()
        if new_total_colored > total_colored:
            total_colored = new_total_colored
            coloring_round += 1
        else:
            stage = "colored"
            coloring_round -= 1
        pbar.update(1)
        if coloring_round > 10000:
            print("coloring_round > 10000, break")
            break
    assert not torch.isnan(colors).any()
    meshes.textures = TexturesVertex(verts_features=[colors])
    return meshes


def multiview_color_projection(meshes: Meshes, image_list: List[Image.Image], cameras_list: List[CamerasBase]=None, camera_focal: float = 2 / 1.35, weights=None, eps=0.05, resolution=1024, device="cuda", reweight_with_cosangle="square", use_alpha=True, confidence_threshold=0.1, complete_unseen=False, below_confidence_strategy="smooth", distract_mask=None) -> Meshes:
    """
    Projects color from a given image onto a 3D mesh.

    Args:
        meshes (pytorch3d.structures.Meshes): The 3D mesh object, only one mesh.
        image_list (PIL.Image.Image): List of images.
        cameras_list (list): List of cameras.
        camera_focal (float, optional): The focal length of the camera, if cameras_list is not passed. Defaults to 2 / 1.35.
        weights (list, optional): List of weights for each image, for ['front', 'front_right', 'right', 'back', 'left', 'front_left']. Defaults to None.
        eps (float, optional): The threshold for selecting visible faces. Defaults to 0.05.
        resolution (int, optional): The resolution of the projection. Defaults to 1024.
        device (str, optional): The device to use for computation. Defaults to "cuda".
        reweight_with_cosangle (str, optional): Whether to reweight the color with the angle between the view direction and the vertex normal. Defaults to None.
        use_alpha (bool, optional): Whether to use the alpha channel of the image. Defaults to True.
        confidence_threshold (float, optional): The threshold for the confidence of the projected color, if final projection weight is less than this, we will use the original color. Defaults to 0.1.
        complete_unseen (bool, optional): Whether to complete the unseen vertex color using laplacian. Defaults to False.

    Returns:
        Meshes: the colored mesh
    """
    # 1. preprocess inputs
    if image_list is None:
        raise ValueError("image_list is None")
    if cameras_list is None:
        raise ValueError("cameras_list is None")
    if weights is None:
        raise ValueError("weights is None, and can not be guessed from image_list")
    
    # 2. run projection
    meshes = meshes.clone().to(device)
    if weights is None:
        weights = [1. for _ in range(len(cameras_list))]
    assert len(cameras_list) == len(image_list) == len(weights)
    original_color = meshes.textures.verts_features_packed()
    assert not torch.isnan(original_color).any()
    texture_counts = torch.zeros_like(original_color[..., :1])
    texture_values = torch.zeros_like(original_color)
    max_texture_counts = torch.zeros_like(original_color[..., :1])
    max_texture_values = torch.zeros_like(original_color)
    for camera, image, weight in zip(cameras_list, image_list, weights):
        ret = project_color(meshes, camera, image, eps=eps, resolution=resolution, device=device, use_alpha=use_alpha)
        if reweight_with_cosangle == "linear":
            weight = (ret['cos_angles'].abs() * weight)[:, None]
        elif reweight_with_cosangle == "square":
            weight = (ret['cos_angles'].abs() ** 2 * weight)[:, None]
        if use_alpha:
            weight = weight * ret['valid_alpha']
        assert weight.min() > -0.0001
        texture_counts[ret['valid_verts']] += weight
        texture_values[ret['valid_verts']] += ret['valid_colors'] * weight
        max_texture_values[ret['valid_verts']] = torch.where(weight > max_texture_counts[ret['valid_verts']], ret['valid_colors'], max_texture_values[ret['valid_verts']])
        max_texture_counts[ret['valid_verts']] = torch.max(max_texture_counts[ret['valid_verts']], weight)

    # Method2
    texture_values = torch.where(texture_counts > confidence_threshold, texture_values / texture_counts, texture_values)
    if below_confidence_strategy == "smooth":
        texture_values = torch.where(texture_counts <= confidence_threshold, (original_color * (confidence_threshold - texture_counts) + texture_values) / confidence_threshold, texture_values)
    elif below_confidence_strategy == "original":
        texture_values = torch.where(texture_counts <= confidence_threshold, original_color, texture_values)
    else:
        raise ValueError(f"below_confidence_strategy={below_confidence_strategy} is not supported")
    assert not torch.isnan(texture_values).any()
    meshes.textures = TexturesVertex(verts_features=[texture_values])

    if distract_mask is not None:
        import cv2
        pil_distract_mask = (distract_mask * 255).astype(np.uint8)
        pil_distract_mask = cv2.erode(pil_distract_mask, np.ones((3, 3), np.uint8), iterations=2)
        pil_distract_mask = Image.fromarray(pil_distract_mask)
        ret = project_color(meshes, cameras_list[0], pil_distract_mask, eps=eps, resolution=resolution, device=device, use_alpha=use_alpha)
        distract_valid_mask = ret['valid_colors'][:, 0] > 0.5
        distract_invalid_index = ret['valid_verts'][~distract_valid_mask]

        # invalid index's neighbors also should included
        L = meshes.laplacian_packed()
        # Convert invalid indices to a boolean mask
        distract_invalid_mask = torch.zeros(meshes.verts_packed().shape[0:1], dtype=torch.bool, device=device)
        distract_invalid_mask[distract_invalid_index] = True
        
        # Find neighbors: multiply Laplacian with invalid_mask and check non-zero values
        # Extract COO format (L.indices() gives [2, N] shape: row, col; L.values() gives values)
        row_indices, col_indices = L.coalesce().indices()
        invalid_rows = distract_invalid_mask[row_indices]
        neighbor_indices = col_indices[invalid_rows]
        
        # Combine original invalids with their neighbors
        combined_invalid_mask = distract_invalid_mask.clone()
        combined_invalid_mask[neighbor_indices] = True

        # repeat
        invalid_rows = combined_invalid_mask[row_indices]
        neighbor_indices = col_indices[invalid_rows]
        combined_invalid_mask[neighbor_indices] = True

        # Apply to texture counts and values
        texture_counts[combined_invalid_mask] = 0
        texture_values[combined_invalid_mask] = 0

    
    if complete_unseen:
        meshes = complete_unseen_vertex_color(meshes, torch.arange(texture_values.shape[0]).to(device)[texture_counts[:, 0] >= confidence_threshold])
    ret_mesh = meshes.detach()
    del meshes
    return ret_mesh


def meshlab_mesh_to_py3dmesh(mesh: ml.Mesh) -> Meshes:
    verts = torch.from_numpy(mesh.vertex_matrix()).float()
    faces = torch.from_numpy(mesh.face_matrix()).long()
    colors = torch.from_numpy(mesh.vertex_color_matrix()[..., :3]).float()
    textures = TexturesVertex(verts_features=[colors])
    return Meshes(verts=[verts], faces=[faces], textures=textures)


def to_pyml_mesh(vertices,faces):
    m1 = ml.Mesh(
        vertex_matrix=vertices.cpu().float().numpy().astype(np.float64),
        face_matrix=faces.cpu().long().numpy().astype(np.int32),
    )
    return m1


def simple_clean_mesh(pyml_mesh: ml.Mesh, apply_smooth=True, stepsmoothnum=1, apply_sub_divide=False, sub_divide_threshold=0.25):
    ms = ml.MeshSet()
    ms.add_mesh(pyml_mesh, "cube_mesh")
    
    if apply_smooth:
        ms.apply_filter("apply_coord_laplacian_smoothing", stepsmoothnum=stepsmoothnum, cotangentweight=False)
    if apply_sub_divide:    # 5s, slow
        ms.apply_filter("meshing_repair_non_manifold_vertices")
        ms.apply_filter("meshing_repair_non_manifold_edges", method='Remove Faces')
        ms.apply_filter("meshing_surface_subdivision_loop", iterations=2, threshold=Percentage(sub_divide_threshold))
    return meshlab_mesh_to_py3dmesh(ms.current_mesh())
