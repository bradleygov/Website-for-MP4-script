#!/usr/bin/env python3
"""Combine multiple MP4 video files into a single MP4.

Uses ffmpeg under the hood. It first attempts a fast, lossless stream copy
(the concat demuxer). If the input clips have mismatched codecs, resolutions,
or frame rates — which the concat demuxer can't handle — it automatically
falls back to re-encoding them into a uniform stream (the concat filter).

Examples:
    # Combine every .mp4 in a folder (sorted naturally) into output.mp4
    python combine_mp4.py ./clips -o output.mp4

    # Combine specific files, in the order given
    python combine_mp4.py intro.mp4 body.mp4 outro.mp4 -o final.mp4

    # Combine using a glob pattern
    python combine_mp4.py "footage/*.mp4" -o reel.mp4

    # Force re-encoding (useful when clips differ but you want to skip the
    # failed fast attempt)
    python combine_mp4.py ./clips -o output.mp4 --reencode
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile


def natural_sort_key(path: str) -> list:
    """Sort key so that 'clip2.mp4' comes before 'clip10.mp4'."""
    name = os.path.basename(path)
    return [int(chunk) if chunk.isdigit() else chunk.lower()
            for chunk in re.split(r"(\d+)", name)]


def resolve_inputs(patterns: list[str], sort: bool) -> list[str]:
    """Expand the given paths/globs/directories into a list of .mp4 files."""
    files: list[str] = []
    for pattern in patterns:
        if os.path.isdir(pattern):
            matched = glob.glob(os.path.join(pattern, "*.mp4"))
            matched += glob.glob(os.path.join(pattern, "*.MP4"))
        elif any(ch in pattern for ch in "*?[]"):
            matched = glob.glob(pattern)
        else:
            matched = [pattern]

        if not matched:
            print(f"warning: no files matched '{pattern}'", file=sys.stderr)
        files.extend(matched)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for f in files:
        real = os.path.abspath(f)
        if real not in seen:
            seen.add(real)
            unique.append(f)

    if sort:
        unique.sort(key=natural_sort_key)

    return unique


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit(
            "error: ffmpeg not found on PATH.\n"
            "Install it first:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: winget install Gyan.FFmpeg  (or https://ffmpeg.org/download.html)"
        )
    return ffmpeg


def write_concat_list(files: list[str], directory: str | None = None) -> str:
    """Write an ffmpeg concat-demuxer list file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8", dir=directory
    ) as list_file:
        for f in files:
            # ffmpeg concat list format: escape single quotes.
            safe = os.path.abspath(f).replace("'", "'\\''")
            list_file.write(f"file '{safe}'\n")
        return list_file.name


def add_progress_flags(cmd: list[str]) -> list[str]:
    """Insert flags that make ffmpeg emit machine-readable progress on stdout.

    Global options must come before the inputs, so they go right after the
    ffmpeg binary. `-progress pipe:1` streams key=value lines (including
    out_time_us) that a caller can parse to compute a percentage.
    """
    return [cmd[0], "-nostats", "-progress", "pipe:1"] + cmd[1:]


def stream_copy_cmd(ffmpeg: str, list_path: str, output: str) -> list[str]:
    """ffmpeg command for a lossless concat-demuxer stream copy."""
    return [
        ffmpeg, "-hide_banner", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output,
    ]


def reencode_cmd(ffmpeg: str, files: list[str], output: str) -> list[str]:
    """ffmpeg command that re-encodes inputs into a uniform H.264/AAC stream."""
    cmd = [ffmpeg, "-hide_banner", "-y"]
    for f in files:
        cmd += ["-i", f]

    n = len(files)
    # Build the filter: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[v][a]
    streams = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    filtergraph = f"{streams}concat=n={n}:v=1:a=1[v][a]"

    cmd += [
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]
    return cmd


def concat_stream_copy(ffmpeg: str, files: list[str], output: str) -> bool:
    """Fast, lossless concat via the demuxer. Returns True on success."""
    list_path = write_concat_list(files)
    try:
        result = subprocess.run(
            stream_copy_cmd(ffmpeg, list_path, output),
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print("stream-copy attempt failed; will try re-encoding.",
                  file=sys.stderr)
            print(result.stderr.strip().splitlines()[-1] if result.stderr else "",
                  file=sys.stderr)
            return False
        return True
    finally:
        os.unlink(list_path)


def concat_reencode(ffmpeg: str, files: list[str], output: str) -> bool:
    """Robust concat via the concat filter. Re-encodes to uniform H.264/AAC."""
    result = subprocess.run(
        reencode_cmd(ffmpeg, files, output),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("error: re-encode concat failed.", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine multiple MP4 files into a single MP4.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "inputs", nargs="+",
        help="MP4 files, glob patterns, or a directory containing .mp4 files.",
    )
    parser.add_argument(
        "-o", "--output", default="combined.mp4",
        help="Output file path (default: combined.mp4).",
    )
    parser.add_argument(
        "--no-sort", action="store_true",
        help="Keep the given order instead of natural-sorting by filename.",
    )
    parser.add_argument(
        "--reencode", action="store_true",
        help="Skip the fast stream-copy attempt and re-encode directly.",
    )
    args = parser.parse_args()

    ffmpeg = find_ffmpeg()

    files = resolve_inputs(args.inputs, sort=not args.no_sort)
    if not files:
        sys.exit("error: no input .mp4 files found.")

    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        sys.exit("error: these inputs do not exist:\n  " + "\n  ".join(missing))

    if len(files) == 1:
        print(f"only one input ({files[0]}); copying to {args.output}.")
        shutil.copyfile(files[0], args.output)
        return 0

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    print(f"Combining {len(files)} files into {args.output}:")
    for i, f in enumerate(files, 1):
        print(f"  {i:>3}. {f}")

    ok = False
    if not args.reencode:
        ok = concat_stream_copy(ffmpeg, files, args.output)
    if not ok:
        print("Re-encoding (this preserves compatibility but is slower)...")
        ok = concat_reencode(ffmpeg, files, args.output)

    if not ok:
        return 1

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"\nDone: {args.output} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
