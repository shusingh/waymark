# Installation & Updates

Waymark is a Python CLI/TUI application. The installed command is `waymark`.
The PyPI distribution name is `waymark-memory` because `waymark` is already
taken on PyPI by another project.

## Recommended Install

Use `pipx` for a CLI app. It keeps Waymark isolated from your system Python
while still exposing the `waymark` command.

=== "Windows PowerShell"

    ```powershell
    py -m pip install --user pipx
    py -m pipx ensurepath
    py -m pipx install waymark-memory
    waymark --version
    waymark today
    ```

=== "macOS"

    ```bash
    brew install pipx
    pipx ensurepath
    pipx install waymark-memory
    waymark --version
    waymark today
    ```

=== "Linux"

    ```bash
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    python3 -m pipx install waymark-memory
    waymark --version
    waymark today
    ```

If `waymark` is not found after installation, open a new terminal so the updated
PATH from `pipx ensurepath` is loaded.

## Current GitHub Release

Install the current public release directly from GitHub:

=== "Windows PowerShell"

    ```powershell
    py -m pip install https://github.com/shusingh/waymark/releases/download/v0.3.2/waymark_memory-0.3.2-py3-none-any.whl
    waymark --version
    ```

=== "macOS / Linux"

    ```bash
    python3 -m pip install https://github.com/shusingh/waymark/releases/download/v0.3.2/waymark_memory-0.3.2-py3-none-any.whl
    waymark --version
    ```

## Optional PDF Import

PDF import needs the optional PDF extra. With PyPI:

=== "Windows PowerShell"

    ```powershell
    py -m pipx inject waymark-memory "waymark-memory[pdf]"
    ```

=== "macOS"

    ```bash
    pipx inject waymark-memory "waymark-memory[pdf]"
    ```

=== "Linux"

    ```bash
    python3 -m pipx inject waymark-memory "waymark-memory[pdf]"
    ```

From a source checkout:

```bash
python -m pip install -e ".[pdf]"
```

## Install from Source

=== "Windows PowerShell"

    ```powershell
    git clone https://github.com/shusingh/waymark.git
    cd waymark
    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev,docs,pdf]"
    waymark --version
    ```

=== "macOS / Linux"

    ```bash
    git clone https://github.com/shusingh/waymark.git
    cd waymark
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev,docs,pdf]"
    waymark --version
    ```

## Update

For a PyPI install:

=== "Windows PowerShell"

    ```powershell
    py -m pipx upgrade waymark-memory
    ```

=== "macOS"

    ```bash
    pipx upgrade waymark-memory
    ```

=== "Linux"

    ```bash
    python3 -m pipx upgrade waymark-memory
    ```

For a GitHub wheel install, install the newer release wheel URL:

```bash
python -m pip install --upgrade https://github.com/shusingh/waymark/releases/download/v0.3.2/waymark_memory-0.3.2-py3-none-any.whl
```

For a source checkout:

```bash
git pull
python -m pip install -e ".[dev,docs,pdf]"
```

## Publishing to PyPI

Waymark uses PyPI Trusted Publishing rather than a long-lived API token. The
project is published from the tag workflow after the trusted publisher is
configured in PyPI.

Use these values:

| Field | Value |
| --- | --- |
| PyPI project name | `waymark-memory` |
| Owner | `shusingh` |
| Repository | `waymark` |
| Workflow file | `pypi.yml` |
| Environment | `pypi` |

After that, maintainers can publish by cutting a release tag. The PyPI workflow
builds the package, checks metadata, verifies the tag matches the package
version, and publishes to PyPI from GitHub Actions.
