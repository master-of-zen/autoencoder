#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import vapoursynth as vs

"""
Autoencoder
"""
def check_executables():
    if not find_executable('ffmpeg'):
        print('No ffmpeg')
        sys.exit()

    if not find_executable('vspipe'):
        print("Can't find vspipe")



def auto_crop():
    pass

def get_media_info(video):

    # make script
    script = "import vapoursynth as vs\n" + \
    "core = vs.get_core()\n" + \
    "video = core.ffms2.Source({video})\n" + \
    "video.set_output()"

    with open('get_media_info.py', 'w') as fl:
        fl.write(script)



if __name__ == "__main__":

    # Check initial requirements
    check_executables()
