Code Guide
===========================

This document briefly introduces the project's directory structure and the functionality of each module. It's mainly to help developers quickly understand the project structure and get a general overview of the overall architecture.
The project is divided into six major modules:

- `desktop`   is the desktop end of the entire project, developed with tauri2, it's a desktop application that integrates all features, including auxiliary management UI functions, installation, logging, update checking, etc.
- `frontend`  is the core UI system of the project, responsible for packaging scripts provided by the server into visual user interfaces, its provided UI is a tab page in desktop.
- `server`    is the server side of the project, responsible for handling all script execution, management, scheduling, monitoring, etc., and also provides plugin mechanisms for feature extension.
- `ssui_components`  are the basic components of the project, responsible for providing basic UI components such as buttons, input boxes, tables, etc.
- `ssui-vscode`  is the project's vscode plugin, responsible for packaging scripts provided by the server into vscode plugins, and providing basic UI components such as buttons, input boxes, tables, etc.
- `extension_builder`  is the project's extension build tool, responsible for creating, packaging, and publishing extensions.

## Server Side

Contains the following directories:

- `server/`       A FastAPI-developed API service, the core of the project
- `ss_executor/`  Responsible for asynchronous script execution
- `ssui/`         The interface for scripts, all scripts depend on this module
- `backend/`      Implementation of project backend logic, `ssui_api` depends on this module

## Extension Features

For different users, SSUI provides different modules as extensions, implementing various AI functionalities.
- `Image` package   Responsible for image-related features, including image generation, editing, sharpening, etc.
- `Video` package   Responsible for video workflows, such as text-to-video, video-to-video, etc.
- `Audio` package   Responsible for audio-related features, including audio generation, video soundtrack matching, etc.
- `3D`    package   Responsible for 3D-related features, including 3D model generation, etc.

Each package has its own API interface, for example, under the Image package:
- `ssui_image`       Contains all image-related wrapper classes for user script calls
- `ssui_image.api`   Contains the actual API interfaces, calling these will immediately execute image generation operations, `ssui_image` depends on this module

## Other Key Directories

- `doc`  is the project's documentation directory, including project design documents, user guides, development documentation, etc.
- `resources`  is a directory for storing models, configurations, and other resources during development, for development and testing only, not included in deployment.
- `examples`  is an example directory containing some example scripts for user reference.
- `extensions/example`  is an example extension 