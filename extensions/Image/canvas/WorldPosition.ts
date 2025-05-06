export interface WorldPositionState {
    x: number;
    y: number;
}

export class WorldPosition {
    private state: WorldPositionState;

    constructor(initialState: WorldPositionState = { x: 0, y: 0 }) {
        this.state = initialState;
    }

    getState(): WorldPositionState {
        return { ...this.state };
    }

    // 移动世界位置
    move(dx: number, dy: number) {
        this.state = {
            x: this.state.x + dx,
            y: this.state.y + dy
        };
    }

    // 设置世界位置
    setPosition(x: number, y: number) {
        this.state = {
            x,
            y
        };
    }

    // 获取世界位置
    getPosition(): WorldPositionState {
        return { ...this.state };
    }
} 