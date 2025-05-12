Extension System
=====================

To combine AI drawing capabilities with various other new technologies, an extension system is essential.
This extension system supports:

1. New server-side APIs - Extensions can add new APIs to the server
2. New callable packages - Python packages in extensions will be automatically added to the Path directory and can be found during execution
3. New UI systems - For a file extension, new UI interfaces can be added and integrated with existing UI through ssui_components

## Extension System Call Logic

First, when the server starts, it scans all subdirectories under extensions (non-recursive scan), listing directories containing ssextension.yaml as extensions.
server/extensions.py contains the extension system loading logic

Then the yaml files in each directory are parsed. Let's briefly explain the meaning of each field:

```
name: ImageExtension    =>  Extension name
version: 0.1.0          =>  Version information
server:
  venv: shared          =>  Which virtual environment to use, default is shared meaning placed in the same virtual environment as other extensions, if there's another custom name, a new virtual environment with that name will be created
  dependencies:
    - numpy>=1.21.2     =>  Dependent packages, versions can be specified
  main: extension.py    =>  Extension entry file, must exist
  packages:
    - ssui_image        =>  Python packages registered by the extension, will be automatically added to Path directory and can be found during execution

web_ui:
  dist: dist/           =>  Extension UI file directory, used to deploy js, css and other static files
```

When reading main: extension.py, this file will be automatically loaded and its code executed. Extensions can add their own APIs in extension.py and load their own Python packages.
The dist directory will automatically create a static file directory, allowing the server to access js, css and other static files.

## Extension System Dependencies

If you write Python code, you might add dependencies to extensions and encounter the following issues. To ensure all extensions use as similar dependencies as possible, our custom build system handles dependency installation during build.
Briefly, the build system scans all extension dependencies and versions, calculates their intersection subset together with the main project's dependencies, then creates a merged requirements.txt file.

Afterwards, a lock file is created to lock dependency versions. Finally during deployment, each extension generates an independent requirements.txt file with locked versions, which can be directly installed by pip.
Through the merge calculation method, we can ensure that when two extensions depend on the same library, the final version is locked to be the same.

## Creating New Extensions

extension_builder is our extension build tool that can create new extensions. It has the following commands:
1. new command, interactively creates a new extension and creates a new directory and corresponding project files in the current folder, refer to ssextension.yaml
2. init command, initializes a project in the current folder, using the folder name as the project name
3. package command, checks if package.json exists, if it exists, executes its package command, then packages the generated js with the current extension's python files, configurations, etc. into a tar.gz

Command line usage:

```
ssext new <extension_name>
ssext init               # Initialize an extension in the current directory
ssext package            # Package the current extension into a tar.gz file
```

To use globally, you can link it to the system:
```
cd extension_builder
npm link
```

To remove when not needed, just unlink.
Note: yarn link seems different, it's better to use npm link

This extension hopes to support interaction with our extension server in the future, for direct publishing and testing of extensions.

## Extension System Upgrades

In the same target SSUI version, if a package version has been locked, even if new extensions are released, that package version won't be upgraded. Only when the next SSUI version is released will all extension dependencies be recalculated and upgraded.
The purpose of this is to ensure all package versions are compatible and tested, avoiding issues like missing symbols after installation.

If you must use a new version, there are two ways:
1. Manually rename the package you want to use and introduce it as a source package
2. Use venv to create a new derived virtual environment, replacing packages in the original environment by installing new ones, but this may cause potential instability, so users need to decide whether to use it

## Extension System Testing

Our officially developed extensions are tested in the build environment to ensure they can be used normally.
Other extension authors need to write their own test cases and upload them together when publishing, for testing in the server test environment. If it fails, failure information will be prompted on the platform, please fix it promptly. 