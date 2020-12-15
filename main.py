#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import vapoursynth as vs
import argparse
from pathlib import Path
import subprocess

"""
Autoencoder
"""
def check_executables():
    """
    Checking is all required executables reachable
    """

    if not find_executable('ffmpeg'):
        print('No ffmpeg')
        sys.exit()

    if not find_executable('vspipe'):
        print("Can't find vspipe")
        sys.exit()


def auto_crop():
    pass


def get_media_info(video):
    """
    Getting media info from input video
    """

    # make script
    if not video.exists():
        print(f"Video {video.as_posix()} is not reachable")
        sys.exit()


    script = "import vapoursynth as vs\n" + \
    "core = vs.get_core()\n" + \
    f"video = core.ffms2.Source('{video.as_posix()}')\n" + \
    "video.set_output()"

    with open('get_media_info.py', 'w') as fl:
        fl.write(script)

    r = subprocess.run(f"vspipe get_media_info.py -i -".split(), capture_output=True)

    print(r.stderr.decode())
    print(r.stdout.decode())

def argparsing():
    """
    Command line parsing and setting default variables
    """

    parser = argparse.ArgumentParser()

    io_group = parser.add_argument_group('Input and Output')
    io_group.add_argument('--input', '-i', type=Path, help='Input File')

    parsed = vars(parser.parse_args())
    return parsed


if __name__ == "__main__":

    # Check initial requirements
    check_executables()
    args = argparsing()
    get_media_info(args.get('input'))
