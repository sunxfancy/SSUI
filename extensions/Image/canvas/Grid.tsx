import React from 'react';
import { Line, Group, Rect } from 'react-konva';
import { Viewport } from './Viewport';

interface GridProps {
    viewport: Viewport;
}

const SMALL_GRID_SIZE = 64;
const LARGE_GRID_SIZE = 512;

export class Grid extends React.Component<GridProps> {
    // 计算网格线的范围
    private calculateGridRange(gridSize: number) {
        const { viewport } = this.props;
        const { position, size, scale } = viewport;

        // 计算视口范围
        const viewLeft = position.x;
        const viewTop = position.y;
        const viewRight = position.x + size.width / scale;
        const viewBottom = position.y + size.height / scale;

        // 计算网格线的起始和结束位置
        const startX = Math.floor(viewLeft / gridSize) * gridSize;
        const endX = Math.ceil(viewRight / gridSize) * gridSize;
        const startY = Math.floor(viewTop / gridSize) * gridSize;
        const endY = Math.ceil(viewBottom / gridSize) * gridSize;

        return { startX, endX, startY, endY };
    }

    // 生成网格线
    private generateGridLines(gridSize: number, isLargeGrid: boolean) {
        const { startX, endX, startY, endY } = this.calculateGridRange(gridSize);
        const lines = [];

        // 生成垂直线
        for (let x = startX; x <= endX; x += gridSize) {
            lines.push(
                <Line
                    key={`v-${x}-${gridSize}`}
                    points={[x, startY, x, endY]}
                    stroke={isLargeGrid ? '#ddd' : '#eee'}
                    strokeWidth={isLargeGrid ? 1 : 0.5}
                />
            );
        }

        // 生成水平线
        for (let y = startY; y <= endY; y += gridSize) {
            lines.push(
                <Line
                    key={`h-${y}-${gridSize}`}
                    points={[startX, y, endX, y]}
                    stroke={isLargeGrid ? '#ddd' : '#eee'}
                    strokeWidth={isLargeGrid ? 1 : 0.5}
                />
            );
        }

        return lines;
    }

    // 生成视口指示器
    private generateViewportIndicator() {
        const { viewport } = this.props;
        const { position, size, scale } = viewport;

        return (
            <Group>
                {/* 视口边界 */}
                <Rect
                    x={position.x}
                    y={position.y}
                    width={size.width / scale}
                    height={size.height / scale}
                    stroke="#ff0000"
                    strokeWidth={2}
                    fill="rgba(255, 0, 0, 0.1)"
                />
            </Group>
        );
    }

    render() {
        return (
            <Group>
                {/* 先渲染小网格 */}
                {this.generateGridLines(SMALL_GRID_SIZE, false)}
                {/* 再渲染大网格 */}
                {this.generateGridLines(LARGE_GRID_SIZE, true)}
                {/* 渲染视口指示器 */}
                {this.generateViewportIndicator()}
            </Group>
        );
    }
} 