# Installation & Updates

Waymark is a Python CLI/TUI application. The recommended public download path is
a [GitHub Release](https://github.com/shusingh/waymark/releases) containing a
wheel and source archive. The current public release is `v0.2.0`.

## Install the public release

Use `pip` with the release wheel URL:

```bash
python -m pip install https://github.com/shusingh/waymark/releases/download/v0.2.0/waymark-0.2.0-py3-none-any.whl
```

If you use `pipx` for isolated command-line tools:

```bash
pipx install https://github.com/shusingh/waymark/releases/download/v0.2.0/waymark-0.2.0-py3-none-any.whl
```

Then run:

```bash
waymark --version
waymark today
```

## Install from source

```bash
git clone https://github.com/shusingh/waymark.git
cd waymark
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

PDF import needs the optional PDF extra:

```bash
python -m pip install -e ".[pdf]"
```

## Update

For a source checkout:

```bash
git pull
python -m pip install -e ".[dev]"
```

For a wheel install, install the newer release wheel URL:

```bash
python -m pip install --upgrade https://github.com/shusingh/waymark/releases/download/v0.1.1/waymark-0.1.1-py3-none-any.whl
```

## Release process

Maintainers create a downloadable package by tagging a version:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The release workflow runs linting, typing, tests, package build, and metadata
checks, then uploads `dist/*` to a GitHub Release.
