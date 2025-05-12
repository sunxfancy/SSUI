Executor
=====================

ss_executor is the executor for Stable Scripts, responsible for executing user scripts. We cannot directly execute user scripts in the server for several considerations:

1. Security concerns: scripts need to run in a secure sandbox, and independent processes can further isolate potential risks
2. Non-blocking design: server needs to handle multiple requests simultaneously, and independent processes can avoid blocking server operation
3. High reliability design: if the executor crashes, the server or UI system can automatically restart the executor, ensuring service reliability
4. Distributed design: executors can be deployed distributedly, for example, deploying multiple executors on multiple machines to improve system throughput
5. Multiple venv support: separated executors can support different torch or other Python library versions in different processes, which is more developer-friendly

## Executor Architecture

The executor is an independent process that communicates with the server through the WebSocket protocol.
The WebSocket server code is mainly in the `ss_executor/scheduler.py` file. This module is loaded by the server to create a WebSocket server listening on port 5000.

The executor startup code is in the `ss_executor/__main__.py` file. This module loads the executor's main function and automatically connects to the server.

## Executor Usage Guide

### 1. Task Definition

The executor defines and executes tasks through Task objects. A Task contains the following main attributes:

- `task_id`: Unique identifier for the task
- `script`: Path to the script to be executed
- `callable`: Name of the specific function to execute
- `params`: Dictionary of parameters to pass to the function
- `details`: Detailed information about the task
- `use_sandbox`: Whether to use sandbox environment (default True)
- `timeout`: Task timeout in seconds (default 300)
- `priority`: Task priority (default 0)

### 2. Executor Registration

The executor automatically registers with the server when starting up, requiring the following information:

- `executor_id`: Unique identifier for the executor
- `host`: Executor host address
- `port`: Executor port
- `max_tasks`: Maximum concurrent tasks (default 1)
- `capabilities`: List of features supported by the executor

### 3. Task Execution Flow

1. Server creates Task object and adds it to task queue
2. Scheduler assigns tasks based on priority and available executors
3. Executor receives task and executes it in sandbox environment
4. After completion, returns TaskResult containing execution result or error information

### 4. Status Management

Task statuses include:
- PENDING: Waiting for execution
- RUNNING: Currently executing
- COMPLETED: Execution completed
- FAILED: Execution failed
- CANCELLED: Cancelled

### 5. Error Handling

- Executor crashes will automatically disconnect
- Task execution timeout will automatically terminate
- Execution failures return detailed error information
- Server can automatically restart executor

### 6. Best Practices

1. Set task priorities appropriately to ensure important tasks are executed first
2. Use sandbox environment for untrusted scripts
3. Set appropriate timeout to avoid infinite task waiting
4. In distributed deployment, assign tasks reasonably based on executor capabilities
5. Regularly check executor status to ensure system stability 