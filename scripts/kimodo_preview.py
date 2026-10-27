"""Render a generated Kimodo skeleton to a small GIF and MP4, no skin assets."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import imageio.v2 as imageio


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('output/kimodo-mac-workflow/motion.npz'))
    args=parser.parse_args()
    metadata=json.loads(args.input.with_name(args.input.stem+'_skeleton.json').read_text())
    with np.load(args.input,allow_pickle=False) as data: points=data['posed_joints']
    parents=metadata['parents']
    # Kimodo NPZ uses meters, Y up. Follow the root horizontally so a long
    # trajectory does not shrink the body to a few pixels. BVH units differ.
    points=points[:,:,[0,2,1]].copy()
    points[:,:,:2]-=points[:,parents.index(-1):parents.index(-1)+1,:2]
    low,high=points.min((0,1)),points.max((0,1))
    center=(low+high)/2
    span=max(high-low)*.62
    fig=plt.figure(figsize=(4,4),dpi=100)
    ax=fig.add_subplot(111,projection='3d')
    fig.patch.set_facecolor('#101827')
    ax.set_facecolor('#101827')
    ax.set(xlim=(center[0]-span,center[0]+span),ylim=(center[1]-span,center[1]+span),zlim=(center[2]-span,center[2]+span))
    ax.set_box_aspect((1,1,1))
    ax.view_init(elev=12,azim=-65)
    ax.set_axis_off()
    ax.set_title(f'Kimodo · MPS · {len(points)/metadata["fps"]:g}s\nRoot-following view',color='white',fontsize=10)
    lines=[(i,p,ax.plot([],[],[],color='#5eead4',linewidth=2.3)[0]) for i,p in enumerate(parents) if p>=0]
    frames=[]
    for pose in points:
        for i,p,line in lines:
            pair=pose[[i,p]]
            line.set_data_3d(pair[:,0],pair[:,1],pair[:,2])
        fig.canvas.draw()
        frames.append(np.asarray(fig.canvas.buffer_rgba())[:,:,:3].copy())
    plt.close(fig)
    output=args.input.with_name('preview')
    imageio.mimsave(str(output)+'.mp4',frames,fps=metadata['fps'],macro_block_size=1)
    imageio.mimsave(str(output)+'.gif',frames,duration=1000/metadata['fps'],loop=0)
    print('Preview:',str(output)+'.gif')


if __name__=='__main__': main()
