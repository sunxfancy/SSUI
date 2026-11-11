# Component 变体

`registerComponentVariant` 从 `ssui_components` 导出，用于为已注册的 component 增加上下文变体。变体在 `ComponentRef` 创建组件时解析，沿用基础组件的类型选择和 Tab，不额外注册为该类型的候选组件。

```tsx
import { registerComponentVariant } from 'ssui_components';

registerComponentVariant({
    name: 'RandomIntegerEditor',
    base: 'IntegerEditor',
    matches: context => context.parameterName === 'seed',
    component: RandomIntegerEditor,
});
```

`base` 指向基础组件的注册名，因此变体自动限定到相应的类型和输入/输出组件。`matches` 接收只读的 `ComponentRefProps`，可以检查 `parameterName`、`type`、`port`、`type_args`、`script_path` 等上下文。`parameterName` 是原始参数名，`name` 是组件注册名；`ComponentTabRef` 会将两者分别传递。

多个变体匹配时，`priority` 较大的优先，默认值为 0；同优先级按注册顺序选择。未匹配时使用基础组件。注册函数返回注销函数，同名注册会替换旧注册。注册应在渲染前完成；变更注册表不会主动触发 React 更新。

变体组件实现与普通组件相同的 `onExecute` / `onUpdate` 和 React ref 协议，可以继承基础组件，也可以独立实现。默认工厂会传递全部上下文和 ref；需要自定义创建逻辑时可提供 `createComponent(ref, props)`。新增变体只需实现组件并注册匹配规则，无需修改基础组件或渲染分支。

首个实现见 `frontend/ssui_components/src/components/Base/RandomIntegerEditor.tsx`。
