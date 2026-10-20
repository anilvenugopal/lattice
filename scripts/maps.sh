#!/usr/bin/env bash
# Fetch the self-hosted basemap (ADR 0013): a Protomaps extract of the United States, and
# the fonts and icons its labels need, into lattice/static/maps/basemap/ (not in git).
# Usage: scripts/maps.sh [--dry-run]     (make maps)
set -euo pipefail

PMTILES_VERSION=1.31.2
BUILD=20261015                         # a daily Protomaps build: build.protomaps.com/$BUILD.pmtiles
ASSETS=028c18f713                      # protomaps/basemaps-assets commit with fonts and sprites
BBOX=-125,24,-66.5,49.5                # the 48 contiguous states
MAXZOOM=10                             # city and county detail; each zoom level is about 4x the size

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHE=$ROOT/.cache/maps
OUT=$ROOT/lattice/static/maps/basemap
mkdir -p "$CACHE" "$OUT"

if [ ! -x "$CACHE/pmtiles" ]; then
  echo "Downloading go-pmtiles $PMTILES_VERSION…"
  curl -fsSL "https://github.com/protomaps/go-pmtiles/releases/download/v$PMTILES_VERSION/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz" \
    | tar -xz -C "$CACHE" pmtiles
fi

if [ "${1:-}" = "--dry-run" ]; then
  "$CACHE/pmtiles" extract "https://build.protomaps.com/$BUILD.pmtiles" "$OUT/us.pmtiles" \
    --bbox="$BBOX" --maxzoom="$MAXZOOM" --dry-run
  exit 0
fi

echo "Extracting the US basemap (zoom 0–$MAXZOOM) from build $BUILD…"
"$CACHE/pmtiles" extract "https://build.protomaps.com/$BUILD.pmtiles" "$OUT/us.pmtiles" \
  --bbox="$BBOX" --maxzoom="$MAXZOOM"

echo "Downloading fonts and icons ($ASSETS)…"
curl -fsSL "https://codeload.github.com/protomaps/basemaps-assets/tar.gz/$ASSETS" -o "$CACHE/assets.tar.gz"
rm -rf "$OUT/fonts" "$OUT/sprites" "$CACHE/assets"
mkdir -p "$CACHE/assets"
tar -xzf "$CACHE/assets.tar.gz" -C "$CACHE/assets" --strip-components=1
mkdir -p "$OUT/fonts"
for font in "Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic"; do
  cp -r "$CACHE/assets/fonts/$font" "$OUT/fonts/"
done
cp -r "$CACHE/assets/sprites" "$OUT/sprites"
du -sh "$OUT"/*
