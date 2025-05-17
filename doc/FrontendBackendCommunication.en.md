Frontend-Backend Communication
=====================

## Basic Communication Flow

1. Frontend calls the prepare interface for script preparation
2. After preparation, calls the execute interface to run specific functions
3. Executor runs the script in a sandbox environment
4. Results are returned to the server in real-time via WebSocket
5. Server returns the results to the frontend

## Main Interfaces

### 1. Script Preparation Interface `/api/prepare`

```python
@app.post("/api/prepare")
async def prepare(script_path: str, callable: str)
```

- Purpose: Prepare before executing the script, collecting all parameters that will be used
- Parameters:
  - script_path: Script path
  - callable: Name of the function to execute

Please refer to the `Configuration System` section in [StableScripts.md](StableScripts.md). After executing this interface, all parameters that will be used will be collected in the `config`.

For practical testing, you can run `yarn dev:server` and `yarn dev:executor` in the project root directory to start the backend and executor, then visit `http://localhost:7422/doc` to find the corresponding interface for testing.
Example parameters: `script_path=<root>/examples/basic/workflow-sd1.py`, `callable=txt2img`

Example response:
```json
{
    "Prompt To Condition": {  // This is the configuration section
        "ignoreLastLayer": {  // This is the configuration key, shown as a configuration item in the UI
            "controler": "Switch",  // Used to find the corresponding UI component
            "args": {},  // UI component parameters
            "default": false  // UI component default value
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

### 2. Script Execution Interface `/api/execute`

```python
@app.post("/api/execute")
async def execute(script_path: str, callable: str, params: Dict[str, Any], details: Dict[str, Any])
```

- Purpose: Execute specific script functions
- Parameters:
  - script_path: Script path
  - callable: Name of the function to execute
  - params: Function parameters
  - details: Task details

Example parameters: `script_path=<root>/examples/basic/workflow-sd1.py`, `callable=txt2img`
```json
{
    "params": {   // All parameters that will be used, key is parameter name
        "model": {  // Parameter creation structure
            "function": "ssui_image.SD1.SD1Model.load",  // Parameter creation function
            "params": {  // Parameter creation function parameter table, must be basic types like string, int, float, bool, list, dict, etc.
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
    "details": {  // All configurations that will be used, key is configuration name
        "Prompt To Condition": {
            "ignoreLastLayer": false // Configuration value
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

Example response:
```json
[ // Return results, can have multiple, representing a list of returned Tuples
    {
        "type": "image",
        "path": "H:\\SSUI\\examples\\basic\\output\\image_20250515201825.png"
    }
]
```

## Backend Parameter Parsing and Execution

After a task is added to the execution queue, the executor retrieves the task from the queue and performs parsing and execution. The specific execution code is in the `_handle_task` function in `ss_executor/__main__.py`.

```python
async def _handle_task(self, websocket, task: Task)
```

### 1. Find the Corresponding Function

```python
func, param_types, return_type = find_callable(loader, task.callable)
```

Here we first need to load the script using `SSLoader`, then find the corresponding function through the `find_callable` function.

### 2. Parse and Create Parameter Table

```python
def convert_param(param: dict): 
    name = param['function']
    params = param['params']

    # Dynamically import and get attributes, supporting arbitrary levels of package/module/class/function access
    parts = name.split('.')
    current = __import__(parts[0])
    for part in parts[1:]:
        current = getattr(current, part)
    return current(**params) # Call function and create parameter

new_params = {}
for name, param in task.params.items():
    new_params[name] = convert_param(param)
```

### 3. Inject Configuration and Execute Function

Next, we need to inject the configuration into `config` to make the UI-modified configurations take effect.

```python
# Inject configuration
loader.config._update = task.details
# Execute
result = func(**new_params)
```

### 4. Convert and Return Results

During the return process, we cannot directly transmit binary images as this would be inefficient. Generally, we save the images locally and only return the image paths.

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