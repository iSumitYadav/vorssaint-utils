#!/usr/bin/env python3
"""Apply the Intel x86_64 support patch to iSumitYadav/vorssaint-utils.

Intended repository location:
    scripts/intel/apply-intel-support.py

Run from any working directory with:
    python3 scripts/intel/apply-intel-support.py

All changes are validated in memory before any source file is written. The
operation is idempotent and relies on Git for review/rollback; it creates no
backup files, keychains, packages, or files outside the repository.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_REMOTE = "github.com/isumityadav/vorssaint-utils"


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def verify_checkout() -> None:
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().lower()
    except (subprocess.CalledProcessError, FileNotFoundError):
        fail(f"{ROOT} is not a Git checkout with an origin remote")
    normalized = remote.removesuffix(".git").rstrip("/")
    if not normalized.endswith(EXPECTED_REMOTE):
        fail(
            f"Unexpected origin: {remote}\n"
            f"This script is specifically for https://{EXPECTED_REMOTE}.git"
        )
    print(f"Verified fork remote: {remote}")


class PlannedFile:
    def __init__(self, relative_path: str):
        self.relative_path = relative_path
        self.path = ROOT / relative_path
        if not self.path.is_file():
            fail(f"Required source file not found: {relative_path}")
        self.original = self.path.read_text(encoding="utf-8")
        self.content = self.original
        self.labels: list[str] = []

    def replace(self, label: str, old: str, new: str) -> None:
        if new in self.content:
            return
        count = self.content.count(old)
        if count != 1:
            fail(
                f"Cannot apply '{label}' in {self.relative_path}: "
                f"expected exactly one old fragment, found {count}. "
                "No source files have been written. Check whether the fork changed."
            )
        self.content = self.content.replace(old, new, 1)
        self.labels.append(label)

    def insert_before(self, label: str, anchor: str, insertion: str, marker: str) -> None:
        if marker in self.content:
            return
        count = self.content.count(anchor)
        if count != 1:
            fail(
                f"Cannot apply '{label}' in {self.relative_path}: "
                f"expected exactly one anchor, found {count}. "
                "No source files have been written. Check whether the fork changed."
            )
        self.content = self.content.replace(anchor, insertion + anchor, 1)
        self.labels.append(label)

    @property
    def changed(self) -> bool:
        return self.content != self.original


def main() -> int:
    verify_checkout()
    files: dict[str, PlannedFile] = {}

    def get(relative_path: str) -> PlannedFile:
        if relative_path not in files:
            files[relative_path] = PlannedFile(relative_path)
        return files[relative_path]

    # build.sh: compile all native targets for Intel Macs running macOS 14+.
    get("build.sh").replace(
        "set native target to x86_64 macOS 15",
        'TARGET="arm64-apple-macosx14.0"',
        'TARGET="x86_64-apple-macosx14.0"',
    )

    selector_path = "Sources/Vorssaint/Services/Metrics/TemperatureSensorSelector.swift"
    selector = get(selector_path)
    selector.replace(
        "add Intel to the CPU platform enum",
        "    case appleM5Family\n",
        "    case appleM5Family\n    case intel\n",
    )
    selector.insert_before(
        "add the documented Intel CPU core sensor map",
        "    static func platform(brandString: String?) -> CPUTemperaturePlatform {",
        '''    // Sensor labels documented by the community Intel x86_64 workaround.\n    private static let intelCPUCoreKeys: Set<String> = [\n        "TC1C", "TC2C", "TC3C", "TC4C",\n    ]\n\n''',
        "private static let intelCPUCoreKeys",
    )
    selector.replace(
        "recognise Intel processor brand strings",
        '        let brand = brandString?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""\n',
        '        let brand = brandString?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""\n'
        '        if brand.range(of: "Intel", options: .caseInsensitive) != nil { return .intel }\n',
    )
    selector.replace(
        "declare Intel as a mapped CPU core set",
        '''        case .appleM1Family, .appleM2Family, .appleM3Family, .appleM4Family,\n             .appleM4ProFamily, .appleM4MaxFamily, .appleM5Family:\n            return true''',
        '''        case .appleM1Family, .appleM2Family, .appleM3Family, .appleM4Family,\n             .appleM4ProFamily, .appleM4MaxFamily, .appleM5Family, .intel:\n            return true''',
    )
    selector.replace(
        "map Intel CPU core sensor keys",
        '''        case .appleM5Family:\n            return appleM5CPUCoreKeys.contains(key)\n        case .unmappedAppleSilicon, .generic:''',
        '''        case .appleM5Family:\n            return appleM5CPUCoreKeys.contains(key)\n        case .intel:\n            return intelCPUCoreKeys.contains(key)\n        case .unmappedAppleSilicon, .generic:''',
    )
    selector.replace(
        "classify Intel TC sensors as CPU and exclude the Intel GPU key",
        '''    static func isCPUTemperatureKey(_ key: String,\n                                    platform: CPUTemperaturePlatform) -> Bool {\n        if key.hasPrefix("Tp") || key.hasPrefix("Te") { return true }''',
        '''    static func isCPUTemperatureKey(_ key: String,\n                                    platform: CPUTemperaturePlatform) -> Bool {\n        if platform == .intel {\n            // TCGC is the Intel GPU sensor, not a CPU temperature sensor.\n            return key.hasPrefix("TC") && key != "TCGC"\n        }\n        if key.hasPrefix("Tp") || key.hasPrefix("Te") { return true }''',
    )

    system_path = "Sources/Vorssaint/Services/SystemMonitor/SystemMonitor.swift"
    system = get(system_path)
    system.replace(
        "discover TCGC alongside other temperature sensors",
        '''            TemperatureSensorSelector.isCPUTemperatureKey(name, platform: cpuTemperaturePlatform)\n                || name.hasPrefix("Tg")\n                || name.range(of: "^TB[0-9]T$", options: .regularExpression) != nil''',
        '''            TemperatureSensorSelector.isCPUTemperatureKey(name, platform: cpuTemperaturePlatform)\n                || name.hasPrefix("Tg") || name == "TCGC"\n                || name.range(of: "^TB[0-9]T$", options: .regularExpression) != nil''',
    )
    system.replace(
        "classify TCGC as a GPU sensor in System Monitor",
        '        gpuKeys = all.filter { $0.name.hasPrefix("Tg") }',
        '        gpuKeys = all.filter { $0.name.hasPrefix("Tg") || $0.name == "TCGC" }',
    )

    fan_path = "Sources/Vorssaint/Services/FanControl/FanControlHardware.swift"
    fan = get(fan_path)
    fan.replace(
        "discover TCGC for fan-control temperature data",
        '''            TemperatureSensorSelector.isCPUTemperatureKey(name, platform: temperaturePlatform)\n                || name.hasPrefix("Tg")''',
        '''            TemperatureSensorSelector.isCPUTemperatureKey(name, platform: temperaturePlatform)\n                || name.hasPrefix("Tg") || name == "TCGC"''',
    )
    fan.replace(
        "classify TCGC as a GPU sensor for fan control",
        '            gpu: keys.filter { $0.name.hasPrefix("Tg") }',
        '            gpu: keys.filter { $0.name.hasPrefix("Tg") || $0.name == "TCGC" }',
    )

    selftest_path = "Sources/Vorssaint/Support/SelfTest.swift"
    selftest = get(selftest_path)
    selftest.replace(
        "include Intel TC keys in the self-test SMC check",
        '            let keys = smc.keys { $0.hasPrefix("Tp") || $0.hasPrefix("Te") || $0.hasPrefix("Tg") }',
        '            let keys = smc.keys { $0.hasPrefix("Tp") || $0.hasPrefix("Te") || $0.hasPrefix("Tg") || $0.hasPrefix("TC") }',
    )
    selftest.replace(
        "include Intel TC keys in the sensor dump",
        '''            name.hasPrefix("Tp") || name.hasPrefix("Te") || name.hasPrefix("Tg")\n                || name.range(of: "^TB[0-9]T$", options: .regularExpression) != nil''',
        '''            name.hasPrefix("Tp") || name.hasPrefix("Te") || name.hasPrefix("Tg")\n                || name.hasPrefix("TC")\n                || name.range(of: "^TB[0-9]T$", options: .regularExpression) != nil''',
    )
    selftest.replace(
        "label TCGC as GPU in the sensor dump",
        '            } else if key.name.hasPrefix("Tg") {',
        '            } else if key.name.hasPrefix("Tg") || key.name == "TCGC" {',
    )

    # Do not write anything until every expected source fragment has validated.
    changed = [item for item in files.values() if item.changed]
    for item in changed:
        item.path.write_text(item.content, encoding="utf-8")

    print("\nPatch summary:")
    if not changed:
        print("  Intel adaptations already appear to be applied; no files changed.")
    else:
        for item in changed:
            print(f"  updated: {item.relative_path}")
            for label in item.labels:
                print(f"    - {label}")
        print(f"\nUpdated {len(changed)} source files.")
    print("Review with: git diff --check && git diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
