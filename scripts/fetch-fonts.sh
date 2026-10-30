#!/usr/bin/env bash
# Downloads Satoshi from Fontshare into the app bundle resources.
# The ITF Free Font License allows embedding Satoshi in your own app but forbids
# redistributing the font files through a public repository, so the file stays gitignored.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

FONTSHARE_URL="${FONTSHARE_SATOSHI_URL:-https://api.fontshare.com/v2/fonts/download/satoshi}"
FONT_DIR="BandLevels/BandLevels/Resources/Fonts"
FONT_FILE="Satoshi-Variable.ttf"
ARCHIVE_PATH="Satoshi_Complete/Fonts/TTF/${FONT_FILE}"

if [[ -f "${FONT_DIR}/${FONT_FILE}" ]]; then
  echo "${FONT_FILE} already present"
  exit 0
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

curl -fsSL -o "${work_dir}/satoshi.zip" "${FONTSHARE_URL}"
unzip -q -j "${work_dir}/satoshi.zip" "${ARCHIVE_PATH}" -d "${work_dir}"
mkdir -p "${FONT_DIR}"
mv "${work_dir}/${FONT_FILE}" "${FONT_DIR}/${FONT_FILE}"
echo "Installed ${FONT_DIR}/${FONT_FILE} (ITF Free Font License, https://www.fontshare.com)"
