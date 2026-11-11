Build System
============================

Our build system is based on yarn and cargo. You need to install nodejs, rust, yarn, and cargo first.

## Basic Build

In the project root directory, executing `yarn` will install all JavaScript dependencies, download a Python environment, create a development virtual environment in the .venv directory, and install all Python dependencies.

You can directly start the desktop project for development:
```
yarn dev:desktop
```

You can also manually start independent development servers:
```
yarn dev:desktop
yarn dev:functional_ui
```
The shared component package has no `dev:components` script; run `yarn build:components` after changing it. `yarn dev:desktop` starts the server and executor automatically when port 7422 is free. For browser-only Functional UI development, run `yarn dev:server`, `yarn dev:executor`, and `yarn dev:functional_ui` separately.

Note: dev:server and dev:executor are not development servers and won't hot reload, but they can help observe their running status and output. You can also check the log folder in the project directory. Additionally, if you manually start dev:server, you must also manually start dev:executor.

## Build Targets

We have 6 main build targets:
- `desktop` - Main desktop project, depends on `functional_ui`, `ssui_components`, `server`, `extension_builder`
- `functional_ui` - Basic UI interface, depends on `ssui_components`
- `ssui_components` - Basic components
- `server` - Server side, depends on `functional_ui`
- `ssui-vscode` - Plugin, depends on `server`, `ssui_components`
- `extension_builder` - Extension build tool

## Build Commands

The project provides multiple build commands:

- `yarn dev:desktop_sb` - Start desktop Storyboard development server for independent React component development
- `yarn dev:desktop` - Start Tauri desktop application development server, **most commonly used**, if port 7422 is not occupied, it will automatically start server and executor
- `yarn dev:server` - Start FastAPI server (port 7422)
- `yarn dev:executor` - Start SSExecutor for task execution and model running
- `yarn dev:functional_ui` - Start functional UI development server (port 7420), when desktop project starts, if port 7420 is occupied, it will automatically use development port 7420 instead of 7422
- `yarn storybook` - Develop UI components independently on port 6006

Build commands:
- `yarn build:desktop` - Build Tauri desktop application
- `yarn build:components` - Build components
- `yarn build:functional_ui` - Build functional UI
- `yarn build:canvas` - Build the Image Canvas frontend
- `yarn build:canvas-engine` - Build the Rust/Wasm Canvas Engine
- `yarn build:desktop_ui` - Build only the desktop frontend, without Tauri/Rust
- `yarn build:example` - Build example extension

## Packaging

Executing `yarn package` will package all code and generate the final installation package in the `desktop/src-tauri/target/release/bundle` directory.

## Extension Packaging

The project supports packaging multiple extensions:
- `yarn ext:package` - Package all extensions
- `yarn ext:package_Image` - Package Image extension
- `yarn ext:package_Video` - Package Video extension
- `yarn ext:package_Audio` - Package Audio extension

## Testing

- `yarn test` - Run Python tests
- `yarn test_on <test_name>` - Run specified test, e.g., `yarn test_on ss_executor_test`
- `yarn test:frontend` / `yarn test:ui` - Frontend unit / browser tests
- `yarn test:desktop-ui` / `yarn test:rust` - Desktop UI / Rust tests
- `yarn test:canvas-engine` - Canvas Engine Cargo tests
- `yarn test:contract` / `yarn api:check` - API contract / OpenAPI type synchronization checks

See the [testing guide](Testing.md) for browser and native test requirements and coverage.

Please note that tests are divided into regular and real-model regression.
Regular tests verify interfaces and flows on CPU with mocked model outputs and
run by default. Real-model regression downloads large models and is off by
default; set `SSUI_RUN_MODEL_TESTS=1` (optionally with `TEST_DATA_DIR`) to run it.

## Dependency Management

- `yarn check_deps` - Check dependency versions
- `yarn requirements` - Generate Python dependency file
- `yarn install-requirements` - Install Python dependencies
- `yarn update-lock` - Update dependency lock file
- `yarn update-lock:no-upgrade` - Update dependency lock file (without upgrading versions, very useful when adding new dependencies)

If you don't want to remember too many commands, just execute `yarn`, it will automatically update and install all dependencies 
