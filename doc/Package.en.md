Project Packaging and Release
===============

## Pre-release Testing

Before releasing a version, all tests must pass, including slow test cases:

```bash
RUN_SLOW_TESTS=1 yarn test
```

## Packaging Process

Please follow these steps for packaging:

1. Compile and link the packaging command-line tool

```bash
yarn build:extension_builder
cd extension_builder && npm link   # This will link the ssext command-line tool globally
```

2. Package all plugins

```bash
yarn ext:package
```

3. Package the project

There are two packaging versions, please choose according to your needs:

```bash
yarn package
yarn package:debug # Debug version, includes complete debugging information, web client can also enable F12 debugging
```

The packaged files are located in the `desktop/src-tauri/target/{debug/release}/bundle` directory.

## Release

For release, use GitHub's release feature to upload the packaged files to the release. 