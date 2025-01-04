import {TrayIcon} from '@tauri-apps/api/tray';
import {Menu} from '@tauri-apps/api/menu';
import { Window } from '@tauri-apps/api/window';
import { defaultWindowIcon } from '@tauri-apps/api/app';

export default async function tray_init() {
    const menu = await Menu.new({
        items: [
            {
                id: 'info',
                text: '关于',
                action: () => {
                    console.log("info press");
                }
            },
            {
                id: 'quit',
                text: '退出',
                action: () => {
                    // 退出逻辑
                    Window.getCurrent().close()
                }
            },
        ],
    });

    let icon = await defaultWindowIcon();
    if (icon) {
        const options = {
            icon: icon,
            menu,
            menuOnLeftClick: false,
            // 托盘行为
            action: (event: any) => {
                switch (event.type) {
                    case 'Click':
                        console.log(
                            `mouse ${event.button} button pressed, state: ${event.buttonState}`
                        );
                        break;
                    case 'DoubleClick':
                        console.log(`mouse ${event.button} button pressed`);
                        break;
                    case 'Enter':
                        console.log(
                            `mouse hovered tray at ${event.rect.position.x}, ${event.rect.position.y}`
                        );
                        break;
                    case 'Move':
                        console.log(
                            `mouse moved on tray at ${event.rect.position.x}, ${event.rect.position.y}`
                        );
                        break;
                    case 'Leave':
                        console.log(
                            `mouse left tray at ${event.rect.position.x}, ${event.rect.position.y}`
                        );
                        break;
                }
            },
        };

        await TrayIcon.new(options);
    }
}

