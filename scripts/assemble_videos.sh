#!/usr/bin/env bash
# Assembles videos/frames/title_N.png + content into videos/step_N.mp4
set -e
cd "$(dirname "$0")/.."

W=1280
H=720

assemble_static() {
  local n=$1
  local content_duration=$2
  ffmpeg -y \
    -loop 1 -t 3 -i "videos/frames/title_${n}.png" \
    -loop 1 -t "${content_duration}" -i "videos/frames/content_${n}.png" \
    -filter_complex "
      [0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1826,setsar=1,fade=t=out:st=2.5:d=0.5[v0];
      [1:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1826,setsar=1,fade=t=in:st=0:d=0.5[v1];
      [v0][v1]concat=n=2:v=1:a=0,format=yuv420p[outv]" \
    -map "[outv]" -r 30 -pix_fmt yuv420p "videos/step_${n}.mp4"
}

assemble_with_recording() {
  local n=$1
  local recording=$2
  ffmpeg -y \
    -loop 1 -t 3 -i "videos/frames/title_${n}.png" \
    -i "${recording}" \
    -filter_complex "
      [0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1826,setsar=1,fade=t=out:st=2.5:d=0.5[v0];
      [1:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1826,setsar=1,fade=t=in:st=0:d=0.5,fps=30[v1];
      [v0][v1]concat=n=2:v=1:a=0,format=yuv420p[outv]" \
    -map "[outv]" -r 30 -pix_fmt yuv420p "videos/step_${n}.mp4"
}

assemble_static 1 6
assemble_static 2 6
assemble_static 3 7
assemble_static 4 7
assemble_static 5 7
assemble_with_recording 6 "videos/raw/step6_recording.mp4"
assemble_static 7 8

echo "All step videos assembled in videos/"
ls -la videos/*.mp4
