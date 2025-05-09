Stable Scripts UI
====================

![quicktest](https://github.com/sunxfancy/SSUI/actions/workflows/quicktest.yml/badge.svg) [中文Readme](Readme.zh.md)

Stable Scripts UI is a web-based user interface for `Stable Scripts` - a kind of python scripts can easily reproduce the same results by other users.


![Desktop Version](doc/images/presentation.png)
![VSCode Plugin](doc/images/vscode-plugin.png)


## Why Stable Scripts?

Comparing to other stable diffusion UI, SSUI has 5 major pros:

- **Easy to use**: Quickly create, run, and share stable scripts, which is self-contained and can automatically download the necessary python modules, AI models and other dependent data.
- **Reproducible**: Scripts, its necessary modules, and the SSUI itself are versioned. Scripts can be run in the exactly same environment as the script author.
- **Management**: Manage your models and configurations 
- **Strong Typed**: All resources (include models) are strong types and can be prevented from being misused.
- **Customizable**: You can customize the scripts, types, models, panels, loaders, ui framework and more.


## Types

- DiffusionModel
  - SD1
  - SDXL
    - Pony
    - Illustrious
  - Flux
- Clip
- VAE
- Latent
- Image
- Mask
- ControlNet
- Conditioning


## Setup Development Environment

### Dependencies

First, please check out the dependencies are installed on your device.

- nodejs and yarn
  - Please download from: https://nodejs.org/en/download
  - npm install --global yarn

- rustc and cargo
  - Please check out https://www.rust-lang.org/tools/install


### Nodejs & Python Environment

The following command will install yarn packages and a embedded python environment in '.venv' and necessary python packages for you.

```bash
yarn
```


### Run Development Server

To quickly start the development, you can run desktop project as the entry point:
```bash
yarn dev:desktop
```

Or start additional hot reload servers for Functional UI development:
```bash
yarn dev:desktop
yarn dev:functional_ui
```

Or you can start the server, executor, functional ui and desktop all manually, which can give you more flexibility, and clear messages:

```bash
yarn dev:server
yarn dev:executor
yarn dev:functional_ui
yarn dev:desktop
```

- Application server: http://localhost:7422/
- API documentation server: http://localhost:7422/docs
- Functional UI dev server: http://localhost:7420/

### Run the example without the desktop project

If you are working on the functional ui, you can run it directly from the web browser:

```bash
yarn dev:server
yarn dev:executor
yarn dev:functional_ui
```

Example URL: 
```
http://localhost:7420/?path=<example_path>/basic/workflow-sd1.py
```

### Download the testing models

To test the image generation, you need the following models, including:

- SD1.5
- SDXL
- Flux

You can download them from:
https://huggingface.co/datasets/sunxfancy/TestSDModels/tree/main
