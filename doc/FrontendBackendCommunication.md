前后端通讯
=====================

## 基本通信流程

1. 前端调用prepare接口进行脚本准备
2. 准备完成后，调用execute接口执行具体函数
3. 执行器在沙盒环境中运行脚本
4. 结果通过WebSocket实时返回给服务器
5. 服务器将结果返回给前端

## 主要接口

### 1. 脚本准备接口 `/api/prepare` 

```python
@app.post("/api/prepare")
async def prepare(script_path: str, callable: str)
```

- 用途：在执行脚本前进行准备工作，收集所有将会用到的参数
- 参数：
  - script_path: 脚本路径
  - callable: 要执行的函数名

请参考 [StableScripts.md](StableScripts.md) 中的 `配置系统` 一节，执行过该接口后，所有将会用到的参数都会被收集到 `config` 中。

具体实践，可以在项目根目录运行 `yarn dev:server` 与 `yarn dev:executor` 启动后端与执行器，然后访问 `http://localhost:7422/doc` 找到对应接口进行测试。
示例参数： `script_path=<root>/examples/basic/workflow-sd1.py`, `callable=txt2img`

示例返回：
```json
{
    "Prompt To Condition": {  // 这里是配置的section
        "ignoreLastLayer": {  // 这里是配置的key, 在UI中表现为一个配置项
            "controler": "Switch",  // 用来寻找对应的UI组件
            "args": {},  // UI组件的参数
            "default": false  // UI组件的默认值
        }
    },
    "Create Empty Latent": {
        "width": {
            "controler": "Slider",
            "args": {
                "min": 512,
                "max": 4096,
                "step": 64,
                "labels": [
                    512,
                    768,
                    1024,
                    1536,
                    1920,
                    2048,
                    3840,
                    4096
                ]
            },
            "default": 512
        },
        "height": {
            "controler": "Slider",
            "args": {
                "min": 512,
                "max": 4096,
                "step": 64,
                "labels": [
                    512,
                    768,
                    1024,
                    1536,
                    1920,
                    2048,
                    3840,
                    4096
                ]
            },
            "default": 512
        }
    },
    "Denoise": {
        "steps": {
            "controler": "Slider",
            "args": {
                "min": 1,
                "max": 100,
                "step": 1,
                "labels": [
                    1,
                    10,
                    20,
                    30,
                    40,
                    50,
                    60,
                    70,
                    80,
                    90,
                    100
                ]
            },
            "default": 30
        },
        "scheduler": {
            "controler": "Select",
            "args": {
                "options": [
                    "ddim",
                    "ddpm",
                    "deis",
                    "deis_k",
                    "lms",
                    "lms_k",
                    "pndm",
                    "heun",
                    "heun_k",
                    "euler",
                    "euler_k",
                    "euler_a",
                    "kdpm_2",
                    "kdpm_2_k",
                    "kdpm_2_a",
                    "kdpm_2_a_k",
                    "dpmpp_2s",
                    "dpmpp_2s_k",
                    "dpmpp_2m",
                    "dpmpp_2m_k",
                    "dpmpp_2m_sde",
                    "dpmpp_2m_sde_k",
                    "dpmpp_3m",
                    "dpmpp_3m_k",
                    "dpmpp_sde",
                    "dpmpp_sde_k",
                    "unipc",
                    "unipc_k",
                    "lcm",
                    "tcd"
                ]
            },
            "default": "ddim"
        },
        "CFG": {
            "controler": "Slider",
            "args": {
                "min": 0,
                "max": 15,
                "step": 0.1
            },
            "default": 7.5
        },
        "seed": {
            "controler": "Random",
            "args": {},
            "default": 123454321
        }
    },
    "Latent to Image": {}
}
```


### 2. 脚本执行接口 `/api/execute`

```python
@app.post("/api/execute")
async def execute(script_path: str, callable: str, params: Dict[str, Any], details: Dict[str, Any])
```

- 用途：执行具体的脚本函数
- 参数：
  - script_path: 脚本路径
  - callable: 要执行的函数名
  - params: 函数参数
  - details: 任务详细信息

示例参数： `script_path=<root>/examples/basic/workflow-sd1.py`, `callable=txt2img`
```json
{
    "params": {   // 所有将会用到的参数，key为参数名
        "model": {  // 参数创建结构体
            "function": "ssui_image.SD1.SD1Model.load",  // 参数创建函数
            "params": {  // 参数创建函数的参数表，必须均为基本类型，如果string, int, float, bool, list, dict等
                "path": "H:\\SSUI_deps\\test_models\\aingdiffusion_v40.safetensors"
            }
        },
        "positive": {
            "function": "ssui.base.Prompt.create",
            "params": {
                "text": "1girl, red dress"
            }
        },
        "negative": {
            "function": "ssui.base.Prompt.create",
            "params": {
                "text": ""
            }
        }
    },
    "details": {  // 所有将会用到的配置，key为配置名
        "Prompt To Condition": {
            "ignoreLastLayer": false // 配置的值
        },
        "Create Empty Latent": {
            "width": 512,
            "height": 512
        },
        "Denoise": {
            "steps": 30,
            "scheduler": "ddim",
            "CFG": 7.5,
            "seed": 756744810
        }
    }
}
```

示例返回结果：
```json
[ // 返回结果，可以有多个，表示返回的Tuple列表
    {
        "type": "image",
        "path": "H:\\SSUI\\examples\\basic\\output\\image_20250515201825.png"
    }
]
```


## 后端参数的解析与执行

在任务被加入到执行队列后，执行器会从队列中获取任务，并进行解析与执行。具体的执行代码在 `ss_executor/__main__.py` 中的 `_handle_task` 函数中。

```python
async def _handle_task(self, websocket, task: Task)
```

### 1. 找到对应的函数

```python
func, param_types, return_type = find_callable(loader, task.callable)
```

这里我们需要首先用 `SSLoader` 加载脚本，然后通过 `find_callable` 函数找到对应的函数。


### 2. 解析并创建参数表

```python
def convert_param(param: dict): 
    name = param['function']
    params = param['params']

    # 动态导入并获取属性,支持任意层级的包/模块/类/函数访问
    parts = name.split('.')
    current = __import__(parts[0])
    for part in parts[1:]:
        current = getattr(current, part)
    return current(**params) # 调用函数并创建参数

new_params = {}
for name, param in task.params.items():
    new_params[name] = convert_param(param)
```

### 3. 注入配置并执行函数

接下来，我们需要将配置注入到 `config` 中，让UI中修改的配置生效。


```python
# 注入配置
loader.config._update = task.details
# 执行
result = func(**new_params)
```

### 4. 转换并返回结果

在返回过程中，我们并不能直接传输二进制的图片，因为这样效率太低了，一般我们是将图片保存在本地，只返回图片的路径。

```python

def convert_return(result):
    if isinstance(result, tuple):
        return [convert_return(r) for r in result]
    
    if isinstance(result, Image):
        current_time = datetime.datetime.now()
        project_root = search_project_root(os.path.dirname(task.script))
        output_dir = os.path.join(project_root, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        path = os.path.join(output_dir, "image_" + current_time.strftime("%Y%m%d%H%M%S") + ".png")
        result._image.save(path)
        return {"type": "image", "path": path}

if not isinstance(result, tuple):
    result = (result,)

result = convert_return(result)
```

