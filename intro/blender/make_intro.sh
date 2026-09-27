#!/usr/bin/env bash
# Render the "ASH SAYS" intro and encode it to MP4 with sound effects.
#
#   ./make_intro.sh "TODAY'S TOPIC" out.mp4 [preview]
#
# Needs a Python with bpy (pip install bpy==4.2.0 imageio-ffmpeg); set PY to it.
# "preview" renders 640x360 @ 12 samples (~10 min on 4 CPUs) instead of
# 1920x1080 @ 32 samples with motion blur.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-python3}"
SUB="${1:-TODAY'S TOPIC}"
OUT="${2:-ash_says_intro.mp4}"
MODE="${3:-final}"
WORK="$(mktemp -d)"

if [ "$MODE" = preview ]; then
  "$PY" "$HERE/intro.py" --out "$WORK/frames" --subtitle "$SUB" --res 640x360 --samples 12
else
  "$PY" "$HERE/intro.py" --out "$WORK/frames" --subtitle "$SUB" --res 1920x1080 --samples 32 --motion-blur
fi
"$PY" "$HERE/sfx.py" "$WORK/sfx.wav"
FFMPEG="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
"$FFMPEG" -y -loglevel error -framerate 24 -i "$WORK/frames/f_%04d.png" -i "$WORK/sfx.wav" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest \
  -movflags +faststart "$OUT"
rm -rf "$WORK"
echo "wrote $OUT"
