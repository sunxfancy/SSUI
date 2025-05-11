Project Architecture
=================

Our overall architecture is based on Tauri for desktop application UI, VSCode plugin as the script developer UI, both connecting to a Python Server managed by Tauri as the event processing center, while Python Executor serves as a distributed task executor that calls our Python package APIs to run AI inference.

```mermaid
graph TB
    subgraph User Interface
        Tauri[Tauri Desktop App<br/>End User UI]
        VSCode[VSCode Plugin<br/>Script Developer UI]
    end
    
    subgraph Server
        Server[Python Server<br/>Event Processing Center]
    end
    
    subgraph Executors
        LocalExecutor[Python Executor<br/>Local AI Inference]
        RemoteExecutor[Python Executor<br/>Remote AI Inference]
    end

    subgraph Inference Framework
        PyTorch[PyTorch Inference<br/>Calling our API packages: ssui, ssui_image, ssui_video, ssui_audio, etc.]
    end
    
    Tauri -->|Event Requests| Server
    VSCode -->|Script Updates| Server
    
    Server -->|Task Distribution| LocalExecutor
    Server -->|Task Distribution| RemoteExecutor
    
    LocalExecutor -->|AI Inference| PyTorch
    RemoteExecutor -->|AI Inference| PyTorch
``` 