export default function envImport() {
    return {
        name: 'env-import',
        transform(code: string, id: string) {
            // 正式环境 && 入口文件
            if (id.endsWith('main.js') && process.env.NODE_ENV === 'production') { // 在代码开头注入 import 语句
                return `import 'ssui_components/dist/style.css';\n${code}`
            }
            return code
        }
    }
}
