Stable Scripts UI
====================

Stable Scripts UI is a web-based user interface for `Stable Scripts` - a kind of python scripts can easily reproduce the same results by other users.

## Features

- **Easy to use**: Quickly create, run, and share scripts, automatically download the necessary modules, models and data.
- **Reproducible**: Scripts and its necessary modules are versioned and can be run in the same environment as the author.
- **Management**: Manage your scripts and its dependencies in a single place
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

```bash
yarn dev
```

Application server: http://127.0.0.1:7422/
API documentation server: http://127.0.0.1:7422/docs
Web UI dev server: http://127.0.0.1:7420/
Example: http://127.0.0.1:7420/script?path=<example_path>