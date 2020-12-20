#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import re
import vapoursynth as vs
import argparse
from pathlib import Path
import subprocess
import json

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

    if not find_executable('mediainfo'):
        print("Can't find mediainfo")
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


def get_tracks_info(video):
    cmd = f'mediainfo --Output=JSON {video.as_posix()}'
    r = subprocess.run(cmd.split(), capture_output=True)

    if len(r.stderr.decode()) > 0:
            print('Error in getting track info')
            print(r.stderr.decode())
            sys.exit()

    track_info = json.loads(r.stdout.decode())


def extract():
    pass


def mux():
    pass


def encode(video):

    anime = ''

    if anime:
        anim = f"--deblock {deblock}"
    else:
        anim = ""

    p2pformat = f'x264 --demuxer y4m --level 4.1 --b-adapt 2 --vbv-bufsize 78125 --vbv-maxrate 62500 --rc-lookahead 250  --me tesa --direct auto --subme 11 --trellis 2 --no-dct-decimate --no-fast-pskip --output encoded.mkv - --ref --min-keyint {fps} --aq-mode 2 --aq-strength {aq} --qcomp {qcomp} {anim} --psy-rd {psy} --bframes 16`'

    vs_pipe = f'vspipe --y4m {vspipe_file} - | x --crf {crf}'

def make_screenshots(video, frame_count, number_of_screenshots):
    pass


def argparsing():
    """
    Command line parsing and setting default variables
    """
    parser = argparse.ArgumentParser()
    io_group = parser.add_argument_group('Input and Output')
    io_group.add_argument('--input', '-i', type=Path, required=True, help='Input File')
    io_group.add_argument('--screenshots', '-s', type=int, required=False, help='Number of screenshots to make')
    parsed = vars(parser.parse_args())
    return parsed


if __name__ == "__main__":

    # Check initial requirements
    check_executables()
    args = argparsing()
    w, h , frames, fps, depth = get_media_info(args.get('input'))
    crops= auto_crop(args.get('input'))
    get_tracks_info(args.get('input'))

