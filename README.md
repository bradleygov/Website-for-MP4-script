# combine_mp4.py

Combine multiple MP4 files into one, fast. Tries a lossless stream copy first; falls back to re-encoding if the clips don't match (codec, resolution, frame rate).

## Install

Requires [ffmpeg](https://ffmpeg.org/) on your PATH.

```
brew install ffmpeg       # macOS
sudo apt install ffmpeg   # Ubuntu
winget install Gyan.FFmpeg  # Windows
```

## Usage

```
# Combine every .mp4 in a folder (sorted naturally)
python combine_mp4.py ./clips -o output.mp4

# Combine specific files, in order
python combine_mp4.py intro.mp4 body.mp4 outro.mp4 -o final.mp4

# Combine using a glob pattern
python combine_mp4.py "footage/*.mp4" -o reel.mp4

# Force re-encoding
python combine_mp4.py ./clips -o output.mp4 --reencode
```

## Flags

| Flag | Description |
|---|---|
| `inputs` | Files, glob patterns, or a directory. Required. |
| `-o, --output` | Output path. Default: `combined.mp4`. |
| `--no-sort` | Keep given order instead of natural-sorting by filename. |
| `--reencode` | Skip the stream-copy attempt and re-encode directly. |

## Site

`combine_mp4 Site.dc.html` is a landing page + CLI reference for this script. Open it directly in a browser.
