# Installation & Updates

Waymark is a Python CLI/TUI application. The recommended public download path
is a [GitHub Release](https://github.com/shusingh/waymark/releases) containing a
wheel and source archive. PyPI publishing can come after the first release once
the package name and release cadence are settled.

## Install from source today

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

## Install a release wheel

After a release tag is pushed, GitHub Actions builds downloadable files under
the repository's **Releases** page. Install the wheel from the release asset:

```bash
python -m pip install waymark-0.1.0-py3-none-any.whl
```

If you use `pipx` for isolated command-line tools:

```bash
pipx install waymark-0.1.0-py3-none-any.whl
```

## Update

For a source checkout:

```bash
git pull
python -m pip install -e ".[dev]"
```

For a wheel install, download the newer release wheel and reinstall it:

```bash
python -m pip install --upgrade waymark-0.1.1-py3-none-any.whl
```

## Release process

Maintainers create a downloadable package by tagging a version:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow runs linting, typing, tests, package build, and metadata
checks, then uploads `dist/*` to a GitHub Release.
