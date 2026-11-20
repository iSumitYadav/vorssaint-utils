# Building Vorssaint on Intel Macs

This document records the community Intel x86_64 adaptations maintained in this fork. It is not an official upstream Intel release.

## Scope

- Target architecture: `x86_64-apple-macosx15.0`
- Minimum deployment target: macOS 15.0
- Build tools: Apple's Xcode Command Line Tools, Swift, Clang, Git, and Python 3
- No Homebrew packages, external Swift packages, or paid Apple Developer account are required for a local ad-hoc-signed build.

## Build on a fresh checkout

```bash
git clone https://github.com/iSumitYadav/vorssaint-utils.git
cd vorssaint-utils
git switch -c intel-macos-x86_64
mkdir -p .tmp scripts/intel docs
grep -qxF '.tmp/' .gitignore || printf '\n# Local temporary build workspace\n.tmp/\n' >> .gitignore
export TMPDIR="$PWD/.tmp"
export DEVELOPER_DIR="/Library/Developer/CommandLineTools"
python3 scripts/intel/apply-intel-support.py
git diff --check
./build.sh --test
./build.sh
```

The script should be placed at `scripts/intel/apply-intel-support.py`. It can be run from any working directory; it locates the repository from its own path and verifies that `origin` points to `iSumitYadav/vorssaint-utils`. The `.tmp/` directory is local-only and ignored by Git; `build/` is already ignored by the repository.

## Intel temperature mapping

The community workaround documents these Intel CPU-core SMC keys:

- `TC1C`
- `TC2C`
- `TC3C`
- `TC4C`

It also documents `TCGC` as an Intel GPU temperature key on the Intel Mac used to develop the workaround.

These labels are not guaranteed to be present on every Intel Mac. Run the built application's `--sensors` diagnostic and validate the keys reported by the specific Mac model before relying on CPU/GPU temperature classification or fan curves.

## Build outputs

The regular build creates the app at:

```text
build/stage/Vorssaint.app
```

The main executable, fan-control helper, and Now Playing adapter are under `build/`:

```text
build/Vorssaint
build/com.vorssaint.utils.fan-control
build/libVorssaintNowPlaying.dylib
```

Verify each binary reports `x86_64` with `file` or `lipo -info`.

## Signing and privacy

For initial testing, use `./build.sh` without `--dev` or `--install`. With no existing Apple Developer ID or project signing identity, the regular build uses ad-hoc signing. The `--dev` and `--install` paths can invoke `Tools/setup-signing.sh`, which creates signing material in the user's Keychains and therefore is not part of the repository-only setup.

Ad-hoc signatures are suitable for local compilation and initial testing, but macOS privacy permissions may not remain trusted across rebuilds. Do not grant permissions until you are ready to run the app as a local installation.

## Cleanup

The source tree, patch script, temporary directory and compiled outputs live in this checkout. The build script also removes its temporary staging directories when it exits. To remove the checkout and its generated files:

```bash
cd ..
rm -rf vorssaint-utils
```

Apple's installed Command Line Tools are intentionally left untouched.

## Maintaining this fork

Keep this document and the patch utility tracked in Git. Commit the Intel source changes on the `intel-macos-x86_64` branch, then push that branch to this fork. Do not commit `.tmp/`, `build/`, local signing keys, or keychain files.

```bash
git add .gitignore docs/INTEL_MACOS_BUILD.md scripts/intel/apply-intel-support.py build.sh Sources/Vorssaint/Services/Metrics/TemperatureSensorSelector.swift Sources/Vorssaint/Services/SystemMonitor/SystemMonitor.swift Sources/Vorssaint/Services/FanControl/FanControlHardware.swift Sources/Vorssaint/Support/SelfTest.swift
git diff --cached --check
git commit -m "Add Intel macOS build support"
git push -u origin intel-macos-x86_64
```
