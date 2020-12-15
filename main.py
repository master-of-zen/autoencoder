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
    """Checking is all required executables reachable"""

    if not find_executable('ffmpeg'):
        print('No ffmpeg')
        sys.exit()

    if not find_executable('vspipe'):
        print("Can't find vspipe")
        sys.exit()


def auto_crop(video):
    """Getting information about how source can be cropped"""

    script = f'ffmpeg -i {video.as_posix()} -vf fps=fps=5,cropdetect -f null -'.split()

    r = subprocess.run(script, capture_output=True)
    output = r.stderr.decode()


    _, _, crop_x, crop_y = [ int(x) for x in re.findall(r"crop=([\d]+):([\d]+):([\d]+):([\d]+)", output)[-1]]
    crop_left = crop_x//2
    crop_right = crop_x//2
    crop_top = crop_y//2
    crop_bottom = crop_y//2
    if crop_left + crop_right + crop_top + crop_bottom == 0:
        print(':: No crop required')
    else:
        print(f":: Crop: {crop_left}:{crop_right}:{crop_top}:{crop_bottom}\nclip = core.std.Crop(clip, left={crop_left}, right={crop_right},top = {crop_top},bottom = {crop_bottom})\n")

    return (crop_left, crop_right, crop_top, crop_bottom)


def get_media_info(video):
    """
    Getting media info from input video
    Width, Height, Frames, Fps
    """
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
    output = r.stdout.decode()

    if len(r.stderr.decode()) > 0:
        print('Error in getting media info')
        print(r.stderr.decode())
        sys.exit()

    w = int(re.findall("Width: ([0-9]+)", output)[0])
    h = int(re.findall("Height: ([0-9]+)", output)[0])
    frames = int(re.findall("Frames: ([0-9]+)", output)[0])
    fps = int(re.findall("FPS: ([0-9]+)", output)[0])
    depth = int(re.findall("Bits: ([0-9]+)", output)[0])
    print(f':: Media info:\n:: {w}:{h} frames:{frames}')
    return w, h, frames, fps, depth


def argparsing():
    """
    Command line parsing and setting default variables
    """
    parser = argparse.ArgumentParser()
    io_group = parser.add_argument_group('Input and Output')
    io_group.add_argument('--input', '-i', type=Path, required=True, help='Input File')
    parsed = vars(parser.parse_args())
    return parsed


if __name__ == "__main__":

    # Check initial requirements
    check_executables()
    args = argparsing()
    w, h , frames, fps, depth = get_media_info(args.get('input'))
    crops= auto_crop(args.get('input'))
