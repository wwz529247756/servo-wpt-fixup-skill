---
name: servo-build
description: Build and run the Servo browser engine from source. Use when pulling the Servo code, bootstrapping dependencies, compiling servoshell (dev/release/custom profiles), switching between Servo versions/tags/commits, cross-compiling, or running the built binary.
---

# Servo Build

Servo is a web browser engine written in Rust, driven by a `mach` build tool (a Python script run through `uv`). Everything below is run from the root of a Servo checkout.

## Prerequisites

- **Rust** via `rustup` — the exact toolchain is pinned per-checkout by `rust-toolchain.toml`; rustup auto-installs it on first build.
- **uv** — used by `mach` to provision the Python environment (see `.python-version` / `pyproject.toml`).
- Platform toolchains:
  - **Windows:** Visual Studio Build Tools (MSVC v143 + Windows SDK) and LLVM/CMake/ninja. `mach bootstrap` installs the rest via `winget` and downloads MSVC/GStreamer deps.
  - **ATL is required:** `mozjs_sys` (SpiderMonkey) needs the ATL/MFC headers — without them the build fails with `ERROR: Cannot find the ATL/MFC headers in the Visual C++ directory`. Install `Microsoft.VisualStudio.Component.VC.ATL` into *every* VS instance used for building (servo's `README.md` lists it):
    ```powershell
    setup.exe modify --add Microsoft.VisualStudio.Component.VC.ATL --quiet
    ```
    VS Installer pitfalls: run the elevated prompt **from the very start** (non-elevated `--quiet` fails with exit 5007 even with an admin-filtered token); `Start-Process -ArgumentList` mangles embedded quotes (exit 87); an elevated process cannot take `-RedirectStandardOutput`. Reliable pattern: write a `.cmd` containing the command with `> log 2>&1`, then `Start-Process -Verb RunAs -Wait <cmd>`.
  - **macOS:** Xcode command-line tools + `brew`.
  - **Linux:** a C toolchain + curl (distro packages), then `mach bootstrap`.

## Getting the code

```bash
git clone https://github.com/servo/servo
cd servo
```

- There are **no git submodules** to initialize.
- To build a specific release/version, check out the tag, branch, or commit you want (see "Building different versions" below).

## Bootstrapping

```bash
./mach bootstrap -y        # Windows: .\mach bootstrap -y
```

Useful flags: `-y/--yes` (answer all prompts), `-f/--force`, `--skip-platform`, `--skip-lints`, `--skip-nextest`, `--ohos`.

This installs platform tooling, the Rust toolchain, MSVC/GStreamer dependencies (Windows), and optional Rust CLI tools (`taplo`, `cargo-deny`, `cargo-nextest`, `crown`). The optional tools are only needed for linting/unit tests — not for `build` or `test-wpt`.

## Building

```bash
./mach build                 # development build (default)
./mach build --release       # optimized build (used for WPT/CI)
./mach build --dev           # explicit dev build
./mach build --profile <p>   # custom Cargo profile (see Cargo.toml)
```

Other flags: `-j N` (parallel jobs), `-v` / `-vv`, `--no-package` (Android), `--use-crown` (JS GC linting), plus any extra args after the flags are passed through to Cargo.

### Where the binary lands

```
target/<profile>/servoshell          # Linux/macOS
target/<profile>/servoshell.exe      # Windows
```

`<profile>` is `debug` for dev builds, `release` for `--release`, or the profile name for `--profile`. On Windows the post-build step copies ANGLE/GStreamer/MSVC DLLs next to the binary — keep them together when moving it.

## Building different versions

```bash
git fetch --tags
git checkout v0.1.3            # or any tag, branch, or commit hash
./mach bootstrap -y            # if deps changed
./mach build --release
```

- `rust-toolchain.toml` pins the Rust version per commit; `mach`/cargo will trigger rustup to install the right toolchain automatically. No manual `rustup` step is needed.
- `.python-version` pins the Python version; `uv` handles it.
- After switching versions, do a clean rebuild when in doubt: `./mach clean` (clears `target/` and the Python venv) or `cargo clean`.

## Running

```bash
./mach run --release https://example.com
./target/release/servoshell https://example.com    # run the binary directly
```

## Cross-compilation / other targets

- `./mach build --android` (or `--target <triple>`) — requires `ANDROID_SDK_ROOT`/`ANDROID_NDK_ROOT`.
- `./mach build --ohos` / `--flavor=<default|harmonyos>` — OpenHarmony.
- `--target <triple>` for arbitrary targets.

Other useful commands: `./mach check`, `./mach package`, `./mach install`, `./mach clean`, `./mach fmt`.

## Slow downloads: mirrors and proxies

If the Rust toolchain or crates.io downloads are slow (e.g. outside your region), point them at a mirror. Backup mirror options you can try:

**Rust toolchain distribution** (set before running rustup/cargo):

```bash
export RUSTUP_DIST_SERVER=https://rsproxy.cn
export RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup
```

**crates.io registry** (add to `~/.cargo/config.toml`):

```toml
[source.crates-io]
replace-with = "mirror"

[source.mirror]
registry = "https://mirrors.tuna.tsinghua.edu.cn/git/crates.io-index.git"
# alternatives:
#   registry = "git://mirrors.ustc.edu.cn/crates.io-index"
#   registry = "https://mirrors.sjtug.sjtu.edu.cn/git/crates.io-index"
#   registry = "git://crates.rustcc.com/crates.io-index"
#   registry = "git://crates.rustcc.cn/crates.io-index"
```

**git clone / pull** — if cloning or pulling the Servo repo (or fetching git dependencies) is slow, configure a git/HTTP proxy:

```bash
git config --global http.proxy http://<your-proxy-host>:<port>
# or per-session:
export HTTP_PROXY=http://<your-proxy-host>:<port>
export HTTPS_PROXY=http://<your-proxy-host>:<port>
```

Set the proxy to whatever address your environment provides; do not hardcode a specific one.

## Troubleshooting

- **`UnicodeEncodeError: 'gbk' codec can't encode character ...`** on non-UTF-8 (e.g. Chinese) Windows consoles: run with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` set (or persist them as user env vars). PowerShell: `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'`.
- **System drive too small** for toolchains/build: relocate `RUSTUP_HOME` and `CARGO_HOME` to a larger drive and update `PATH` accordingly.
- **`lld-link` / linker not found** on Windows: ensure the LLVM `bin` directory is on `PATH` (Servo's `.cargo/config.toml` uses `lld-link.exe`).
