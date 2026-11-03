import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { MeshArtifact } from './MeshArtifact';

function Preview({ boundary = false, degenerate = false }: { boundary?: boolean; degenerate?: boolean }) {
    const ref = React.useRef<MeshArtifact>(null);
    React.useEffect(() => { ref.current?.onUpdate({
        path: '/mock/generated.glb', format: 'glb', quality: {
            parts: 2, quads: 128, removed_zero_area_faces: 3, regularized_faces: 1,
            degenerate_export_triangles: degenerate ? 2 : 0,
            boundary_edges: boundary ? 8 : 0, boundary_edges_away_from_input: boundary ? 2 : 0,
            nonmanifold_edges: 0,
        },
    }); }, [boundary, degenerate]);
    return <MeshArtifact ref={ref} />;
}
const meta = { title: 'Shared/Mesh quality', component: Preview } satisfies Meta<typeof Preview>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Ready: Story = {};
export const OpenBoundary: Story = { args: { boundary: true } };
export const Degenerate: Story = { args: { degenerate: true } };
