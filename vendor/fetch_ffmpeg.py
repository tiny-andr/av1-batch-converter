"""Download the ffmpeg build that gets bundled into the exe.

ffmpeg.exe is ~98 MB, so it is vendored rather than committed. Run this once
before building; build.bat calls it automatically when the file is missing.

The download is pinned to an exact gyan.dev release and verified against both
the archive's published SHA-256 and the extracted binary's own SHA-256, so a
silently swapped upstream build fails loudly instead of shipping.

Usage:
    python vendor/fetch_ffmpeg.py            # skip if already present
    python vendor/fetch_ffmpeg.py --force    # re-download
    python vendor/fetch_ffmpeg.py --list     # show what is pinned
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request

# Pinned upstream artifacts. Update all four together when bumping ffmpeg.
BUILD = "9.0.1-essentials_build"
ARCHIVE_URL = ("https://www.gyan.dev/ffmpeg/builds/packages/"
               "ffmpeg-9.0.1-essentials_build.7z")
ARCHIVE_SHA256 = "49a73bdf0850092a252ac4641d922f3048d63ed113e196cc65ce1e4f7fb33e85"
FFMPEG_SHA256 = "72a489eccd008c2ec2c0a5856c5c75bc3d8bbfa90166c4566865c246445e6aa3"

ARCHIVE_NAME = os.path.basename(ARCHIVE_URL)
INNER_DIR = "ffmpeg-9.0.1-essentials_build"
MEMBERS = [
    (INNER_DIR + r"\bin\ffmpeg.exe", "ffmpeg.exe"),
    (INNER_DIR + r"\LICENSE", "LICENSE"),
    (INNER_DIR + r"\README.txt", "README-ffmpeg.txt"),
]

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "ffmpeg")
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path):
    """Fetch with a browser-ish User-Agent.

    gyan.dev sits behind Cloudflare and answers a bare urllib request with 503,
    so the UA is not optional here.
    """
    opener = urllib.request.build_opener()
    if PROXY:
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    with opener.open(url, timeout=600) as src, open(path, "wb") as dst:
        total = int(src.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            dst.write(chunk)
            done += len(chunk)
            if total:
                sys.stdout.write("\r  %5.1f%% of %.1f MB"
                                 % (100.0 * done / total, total / 1048576.0))
                sys.stdout.flush()
    sys.stdout.write("\n")


def find_seven_zip():
    for candidate in (SEVEN_ZIP, shutil.which("7z"), shutil.which("7za")):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="re-download even if ffmpeg.exe is present")
    parser.add_argument("--list", action="store_true",
                        help="print the pinned build and exit")
    args = parser.parse_args()

    if args.list:
        print("build   : %s" % BUILD)
        print("archive : %s" % ARCHIVE_URL)
        print("  sha256: %s" % ARCHIVE_SHA256)
        print("ffmpeg  : %s" % FFMPEG_SHA256)
        return 0

    target = os.path.join(DEST, "ffmpeg.exe")
    if os.path.isfile(target) and not args.force:
        got = sha256(target)
        if got == FFMPEG_SHA256:
            print("ffmpeg.exe already present and verified (%s)"
                  % got[:16] + "...")
            return 0
        print("ffmpeg.exe present but its hash does not match the pin")
        print("  expected %s" % FFMPEG_SHA256)
        print("  actual   %s" % got)
        return 1

    seven = find_seven_zip()
    if not seven:
        print("7-Zip not found. Install it, or unpack %s manually so that\n"
              "  %s\nand the LICENSE / README beside it exist." % (ARCHIVE_NAME, target))
        return 1

    os.makedirs(DEST, exist_ok=True)
    cache = os.path.join(DEST, ARCHIVE_NAME)

    if not os.path.isfile(cache):
        print("downloading %s" % ARCHIVE_URL)
        download(ARCHIVE_URL, cache)
    else:
        print("using cached %s" % cache)

    got = sha256(cache)
    if got != ARCHIVE_SHA256:
        print("archive hash mismatch, refusing to use it")
        print("  expected %s" % ARCHIVE_SHA256)
        print("  actual   %s" % got)
        os.remove(cache)
        return 1
    print("archive sha256 verified")

    for inner, name in MEMBERS:
        result = subprocess.run(
            [seven, "e", cache, inner, "-o" + DEST, "-y"],
            capture_output=True, text=True)
        if result.returncode != 0:
            print("could not extract %s\n%s" % (inner, result.stdout))
            return 1

    got = sha256(target)
    if got != FFMPEG_SHA256:
        print("extracted ffmpeg.exe hash mismatch")
        print("  expected %s" % FFMPEG_SHA256)
        print("  actual   %s" % got)
        return 1

    os.remove(cache)
    print("ffmpeg.exe extracted and verified: %.1f MB" % (os.path.getsize(target) / 1048576.0))
    print("  %s" % FFMPEG_SHA256)
    return 0


if __name__ == "__main__":
    sys.exit(main())
