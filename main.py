#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import re
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
    """
    Getting information about how source can be cropped
    """


def get_media_info(video):
    """
    Getting media info from input video
    Width, Height, Frames, Fps
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


    if len(r.stderr.decode()) > 0:
        print('Error in getting media info')
        print(r.stderr.decode())
        sys.exit()

    output = r.stdout.decode()
    # print(output)

    w = int(re.findall("Width: ([0-9]+)", output)[0])
    h = int(re.findall("Height: ([0-9]+)", output)[0])
    frames = int(re.findall("Frames: ([0-9]+)", output)[0])
    fps = int(re.findall("FPS: ([0-9]+)", output)[0])
    depth = int(re.findall("Bits: ([0-9]+)", output)[0])
    return w, h, frames, fps, depth

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
    print(get_media_info(args.get('input')))
