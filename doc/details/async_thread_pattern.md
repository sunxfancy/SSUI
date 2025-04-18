# 异步函数中使用后台线程的模式

## 背景

在异步编程中，我们经常需要处理一些耗时的操作（如文件系统操作、网络请求等）。如果这些操作直接在异步函数中执行，会阻塞整个事件循环。为了解决这个问题，我们可以使用后台线程来处理这些耗时操作，同时保持与主事件循环的通信。

## 模式说明

### 基本结构

```python
async def async_function():
    # 获取主事件循环
    loop = asyncio.get_event_loop()
    
    def background_task():
        try:
            # 执行耗时操作
            result = do_heavy_work()
            
            # 使用主事件循环发送回调
            loop.call_soon_threadsafe(callback, result)
            
        except Exception as e:
            # 错误处理
            loop.call_soon_threadsafe(error_callback, str(e))
    
    # 启动后台线程
    thread = threading.Thread(target=background_task)
    thread.start()
    
    return {"message": "Task started"}
```

### 关键点

1. **事件循环获取**
   - 在异步函数内部使用 `asyncio.get_event_loop()` 获取主事件循环
   - 不要将事件循环作为参数传递，而是在函数内部获取

2. **线程安全通信**
   - 使用 `loop.call_soon_threadsafe()` 确保回调在主事件循环中执行
   - 避免在后台线程中直接调用异步函数

3. **错误处理**
   - 在后台线程中捕获所有异常
   - 使用 `call_soon_threadsafe` 将错误信息传回主线程

## 使用场景

- 文件系统操作（如扫描目录、读写大文件）
- 耗时的计算任务
- 需要保持响应性的后台任务

## 示例代码

```python
async def scan_models(
    self,
    scan_dir: str,
    client_id: str,
    request_uuid: str,
    callback: Callable[[str, str, Dict[str, Any]], None],
    finish_callback: Callable[[str, str, Dict[str, Any]], None]
) -> Dict[str, Any]:
    # 获取主事件循环
    loop = asyncio.get_event_loop()
    
    def scan_target_dir():
        try:
            # 执行文件系统操作
            for root, _, files in os.walk(scan_dir):
                for file in files:
                    if file.endswith(('.safetensors', '.pt', '.ckpt')):
                        # 处理文件...
                        
                        # 发送回调到主线程
                        loop.call_soon_threadsafe(
                            callback, 
                            client_id, 
                            request_uuid, 
                            callback_data
                        )
            
            # 发送完成回调
            loop.call_soon_threadsafe(
                finish_callback, 
                client_id, 
                request_uuid, 
                finish_data
            )
            
        except Exception as e:
            # 错误处理
            loop.call_soon_threadsafe(
                finish_callback, 
                client_id, 
                request_uuid, 
                error_data
            )
    
    # 启动后台线程
    thread = threading.Thread(target=scan_target_dir)
    thread.start()
    
    return {"message": "Model scan started"}
```

## 注意事项

1. 确保在异步函数内部获取事件循环，而不是通过参数传递
2. 所有与主线程的通信都必须通过 `call_soon_threadsafe`
3. 后台线程中的异常必须被捕获并传回主线程
4. 避免在后台线程中直接使用异步函数或协程
5. 考虑线程的生命周期管理，必要时实现清理机制

## 最佳实践

1. 保持后台线程的职责单一，只处理特定的耗时操作
2. 使用清晰的错误处理机制
3. 提供适当的进度反馈
4. 考虑实现取消机制
5. 注意资源清理 