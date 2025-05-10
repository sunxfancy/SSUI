import { produce, immerable } from "immer";

export class WorldPosition {
    [immerable] = true;
    public x: number;
    public y: number;

    constructor(x: number, y: number) {
        this.x = x;
        this.y = y;
    }

    // 移动世界位置
    move(dx: number, dy: number) {
        return produce(this, draft => {
            draft.x = draft.x + dx;
            draft.y = draft.y + dy;
        });
    }

    // 设置世界位置
    setPosition(x: number, y: number) {
        return produce(this, draft => {
            draft.x = x;
            draft.y = y;
        });
    }

} 