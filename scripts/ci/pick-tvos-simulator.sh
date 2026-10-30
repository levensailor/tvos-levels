#!/usr/bin/env bash
# Prints the UDID of an available Apple TV simulator, creating one if needed.
set -euo pipefail

find_device() {
  xcrun simctl list devices available -j | python3 -c '
import json, sys
devices = json.load(sys.stdin)["devices"]
for runtime in sorted(devices, reverse=True):
    if "tvOS" not in runtime:
        continue
    for device in devices[runtime]:
        if device.get("isAvailable") and device["name"].startswith("Apple TV"):
            print(device["udid"])
            sys.exit(0)
'
}

udid="$(find_device || true)"
if [[ -z "${udid}" ]]; then
  echo "No tvOS simulator found; downloading the tvOS platform" >&2
  xcodebuild -downloadPlatform tvOS >&2
  runtime="$(xcrun simctl list runtimes -j | python3 -c '
import json, sys
runtimes = [r for r in json.load(sys.stdin)["runtimes"] if r["platform"] == "tvOS" and r["isAvailable"]]
print(sorted(runtimes, key=lambda r: r["version"])[-1]["identifier"])
')"
  udid="$(xcrun simctl create "Apple TV CI" com.apple.CoreSimulator.SimDeviceType.Apple-TV-4K-3rd-generation-4K "${runtime}")"
fi
echo "${udid}"
