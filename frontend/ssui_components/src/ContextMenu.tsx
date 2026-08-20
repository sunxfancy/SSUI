import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Menu, MenuDivider, MenuItem } from "@blueprintjs/core";

export interface ContextMenuItem {
    /** 菜单项文本；缺省时渲染为分隔线（可与 dividerBefore 组合使用） */
    label?: string;
    icon?: React.ComponentProps<typeof MenuItem>["icon"];
    disabled?: boolean;
    intent?: React.ComponentProps<typeof MenuItem>["intent"];
    dividerBefore?: boolean;
    onClick?: () => void;
}

export interface ContextMenuProps {
    x: number;
    y: number;
    items: ContextMenuItem[];
    onClose: () => void;
    className?: string;
}

/**
 * 通用浮动右键菜单：在指定屏幕坐标渲染一个 Blueprint 菜单，
 * 点击菜单外、按 Escape、窗口滚动或失焦时自动关闭。
 */
export const ContextMenu: React.FC<ContextMenuProps> = ({
    x,
    y,
    items,
    onClose,
    className,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleMouseDown = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                onClose();
            }
        };
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose();
            }
        };
        const handleClose = () => onClose();

        window.addEventListener("mousedown", handleMouseDown);
        window.addEventListener("keydown", handleKeyDown);
        window.addEventListener("resize", handleClose);
        window.addEventListener("blur", handleClose);
        window.addEventListener("scroll", handleClose, true);

        return () => {
            window.removeEventListener("mousedown", handleMouseDown);
            window.removeEventListener("keydown", handleKeyDown);
            window.removeEventListener("resize", handleClose);
            window.removeEventListener("blur", handleClose);
            window.removeEventListener("scroll", handleClose, true);
        };
    }, [onClose]);

    if (items.length === 0) {
        return null;
    }

    // 粗略估算菜单高度，用于防止菜单超出视口底部
    const estimatedHeight = items.reduce((sum, item) => sum + (item.dividerBefore ? 9 : 30), 8);
    const left = Math.min(Math.max(x, 4), window.innerWidth - 220);
    const top = Math.min(Math.max(y, 4), window.innerHeight - estimatedHeight);

    const menu = (
        <div
            ref={containerRef}
            className={className}
            style={{
                position: "fixed",
                left,
                top,
                zIndex: 3000,
                background: "#ffffff",
                borderRadius: 6,
                boxShadow: "0 2px 12px rgba(0, 0, 0, 0.25)",
            }}
            onContextMenu={(e) => e.preventDefault()}
        >
            <Menu>
                {items.map((item, index) => {
                    if (!item.label) {
                        return <MenuDivider key={index} />;
                    }

                    const menuItem = (
                        <MenuItem
                            key={index}
                            text={item.label}
                            icon={item.icon}
                            disabled={item.disabled}
                            intent={item.intent}
                            onClick={() => {
                                onClose();
                                item.onClick?.();
                            }}
                        />
                    );

                    return item.dividerBefore ? (
                        <React.Fragment key={index}>
                            <MenuDivider />
                            {menuItem}
                        </React.Fragment>
                    ) : (
                        menuItem
                    );
                })}
            </Menu>
        </div>
    );

    // 通过 Portal 渲染到 body，避免父级 overflow / filter / backdrop-filter 造成的裁剪与定位偏差
    return createPortal(menu, document.body);
};

export default ContextMenu;
