#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import re
import vapoursynth as vs
import argparse
from pathlib import Path
from subprocess import Popen
import subprocess
import json
from pprint import PrettyPrinter
import os
import shlex
pp = PrettyPrinter(indent=2).pprint


"""
Autoencoder
"""

class Autoencoder:

    def __init__(self):
        self.args = None
        self.input = None
        self.output = None
        self.tracks = None
        self.audio_tracks = []
        self.subtitle_tracks = []
        self.crop = ''
        self.ffmpeg_crop = ''
        self.desync_frames = 0

    def argparsing(self):
        """
        Command line parsing and setting default variables
        """
        parser = argparse.ArgumentParser()
        io_group = parser.add_argument_group('Input and Output')
        io_group.add_argument('--input', '-i', type=Path, required=True, help='Input File')
        io_group.add_argument('--output', '-o', type=Path, help="Output file name")
        io_group.add_argument('--screenshots', '-s', type=int, required=False, help='Number of screenshots to make')
        self.args = vars(parser.parse_args())
        self.input = self.args['input']

        if self.args['output']:
            self.output = self.args['output']
        else:
            self.output = Path(self.args['input']).with_suffix('.mkv')


    def check_executables(self):
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


    def auto_crop(self):
        """Getting information about how source can be cropped"""

        script = f'ffmpeg -i {self.input.as_posix()} -vf fps=fps=5,cropdetect -f null -'.split()

        r = subprocess.run(script, capture_output=True)
        output = r.stderr.decode()


        _, _, crop_x, crop_y = [ int(x) for x in re.findall(r"crop=([\d]+):([\d]+):([\d]+):([\d]+)", output)[-1]]

        self.ffmpeg_crop = re.findall(r"(crop=+.*)", output)[-1]

        crop_left = crop_x
        crop_right = crop_x
        crop_top = crop_y
        crop_bottom = crop_y
        if crop_left + crop_right + crop_top + crop_bottom == 0:
            print(':: No crop required')
        else:
            print(f":: Autocrop Detected")
            self.crop = f'video = core.std.Crop(video, left={crop_left}, right={crop_right},top = {crop_top},bottom = {crop_bottom})'

        return (crop_left, crop_right, crop_top, crop_bottom)


    def get_media_info(self):
        """
        Getting media info from input video
        Width, Height, Frames, Fps
        """
        if not self.input.exists():
            print(f"Video {self.input.as_posix()} is not reachable")
            sys.exit()

        script = "import vapoursynth as vs\n" + \
        "core = vs.get_core()\n" + \
        f"video = core.ffms2.Source('{self.input.as_posix()}')\n" + \
        "video.set_output()"

        with open('get_media_info.py', 'w') as fl:
            fl.write(script)

        r = subprocess.run(f"vspipe get_media_info.py -i -".split(), capture_output=True)
        output = r.stdout.decode()

        if len(r.stderr.decode()) > 0:
            print('Error in getting media info')
            print(r.stderr.decode())
            sys.exit()

        os.remove('get_media_info.py')

        w = int(re.findall("Width: ([0-9]+)", output)[0])
        h = int(re.findall("Height: ([0-9]+)", output)[0])
        frames = int(re.findall("Frames: ([0-9]+)", output)[0])
        fps = int(re.findall("FPS: ([0-9]+)", output)[0])
        depth = int(re.findall("Bits: ([0-9]+)", output)[0])
        print(f':: Media info:\n:: {w}:{h} frames:{frames}')
        return w, h, frames, fps, depth

    def extract(self):

        Path("Audio").mkdir(parents=True, exist_ok=True)

        audio = [x for x in self.tracks if x['@type'] == "Audio"]
        #pp(audio[0])
        print(':: Extracting Audio')
        for x in audio:
            track = f'Audio/{x["@typeorder"]}.mkv'
            self.audio_tracks.append(track)
            cmd = f'mkvextract -q {Path(self.input).as_posix()} tracks {x["@typeorder"]}:{track}'.split()
            Popen(cmd).wait()

        print(':: Audio Extracted')


        Path("Subtitles").mkdir(parents=True, exist_ok=True)

        #pp(self.tracks)
        subtitles = [x for x in self.tracks if x['@type'] == "Text"]

        print(':: Extracting Subtitles')

        # TODO: fix extracting audio and not subs
        for x in subtitles:
            #print(x)
            track = f'Subtitles/{x["StreamOrder"]}.srt'
            self.audio_tracks.append(track)
            cmd = f'mkvextract -q {Path(self.input).as_posix()} tracks {x["StreamOrder"]}:{track}'.split()
            Popen(cmd).wait()

        print(':: Subtitles Extracted')

    def get_tracks_info(self):
        cmd = f'mediainfo --Output=JSON {self.input.as_posix()}'
        r = subprocess.run(cmd.split(), capture_output=True)

        if len(r.stderr.decode()) > 0:
                print('Error in getting track info')
                print(r.stderr.decode())
                sys.exit()

        self.tracks = json.loads(r.stdout.decode())['media']['track']

        #pp(self.tracks)

    def merge(self):

        print(':: Mergin end result')

        to_merge = ' '.join(self.audio_tracks) + ' '.join(self.subtitle_tracks)

        cmd = f'mkvmerge -q -o {self.output} encoded.mkv {to_merge}'

        Popen(cmd.split()).wait()

        print(':: All done!')

    def detect_desync(self):

        print(":: Detecting desync")

        # Making source referense screenshot
        Path("Temp").mkdir(parents=True, exist_ok=True)
        cmd_source = f"ffmpeg -y -loglevel warning -hide_banner -i {self.input} -an -sn -dn -filter_complex " + "'select=eq(n\\,1710)'," + f"{self.ffmpeg_crop} -frames:v 1 Temp/ref.png "
        #print(cmd_source)

        Popen(shlex.split(cmd_source)).wait()
        #print(":: Source screenshot made")


        # encoded.mkv
        # Making encoded screenshot
        cmd_enc = f"ffmpeg -y -hide_banner -loglevel warning -i encoded.mkv -an -sn -dn -filter_complex " + "'select=between(n\\,1705\\,1715)',setpts=PTS-STARTPTS," + f"{self.ffmpeg_crop}  Temp/%03d.png "
        #print(cmd_enc)
        Popen(shlex.split(cmd_enc)).wait()
        #print(":: Encoded screenshots made")

        #r = subprocess.run(script, capture_output=True)
        #output = r.stderr.decode()

        # Sync frame is 6

        # [('001.png', 22.1255), ('002.png', 23.231239), ('003.png', 24.808687), ('004.png', 26.775733), ('005.png', 29.99033), ('006.png', 'infinite'), ('007.png', 30.340453), ('008.png', 27.589498), ('009.png', 25.867822), ('010.png', 24.417369), ('011.png', 23.194266)]

        flist = []
        for p in Path('Temp').iterdir():
            if p.is_file() and 'ref' not in p.name:
                #print(p)
                script = f"ffmpeg -hide_banner -i {p}  -i Temp/ref.png -filter_complex psnr -f null -"
                r = subprocess.run(shlex.split(script), capture_output=True)
                output = r.stderr.decode()
                #print(output)
                if 'inf' in output:
                    score = 'infinite'
                else:
                    score = float(re.findall(r"average:(\d+.\d+)", output)[-1])

                tp = (int(p.stem) - 6, score)
                flist.append(tp)
        self.desync_frames =  max(flist, key=lambda x: x[1])[0]

        if self.desync_frames == 0:
            print(":: No desync detected")
        else:
            print(f":: Detected desync: {self.desync_frames} frame(s)")

    def encode(self):

        anime = ''

        if anime:
            deblock = -1
            anim = f"--deblock {deblock}"
        else:
            anim = ""

        crf= 30
        fps= 240
        aq= 1
        psy= 30

        p2pformat = f'x264 --log-level error -  --preset superfast --demuxer y4m --output encoded.mkv'

        #p2pformat = f'x264 --log-level error --preset superfast --demuxer y4m --level 4.1 --b-adapt 2 --vbv-bufsize 78125 --vbv-maxrate 62500 --rc-lookahead 250  --me tesa --direct auto --subme 11 --trellis 2 --no-dct-decimate --no-fast-pskip --output encoded.mkv - --ref 6 --min-keyint {fps} --aq-mode 2 --aq-strength {aq} --qcomp 0.62 {anim} --psy-rd {psy} --bframes 16 '

        script = "import vapoursynth as vs\n" + \
        "core = vs.get_core()\n" + \
        f"video = core.ffms2.Source('{self.input.as_posix()}')\n" + \
        self.crop + '\n'\
        "video.set_output()"



        with open('settings.py', 'w') as w:
            w.write(script)



        vs_pipe = f'vspipe --y4m settings.py - '
        enc =  f'{p2pformat} --crf {crf} '


        print(':: Encoding..\r')
        pr = Popen(vs_pipe.split(), stdout=subprocess.PIPE,stderr=subprocess.PIPE )

        en = Popen(enc.split(), stdin=pr.stdout).wait()

        print(':: Encoded')

    def make_screenshots(self, video, frame_count, number_of_screenshots):
        pass


if __name__ == "__main__":

    encoder = Autoencoder()
    # Check initial requirements
    encoder.check_executables()
    encoder.argparsing()
    encoder.get_media_info()
    encoder.auto_crop()
    encoder.get_tracks_info()
    encoder.extract()
    encoder.encode()
    encoder.merge()
    encoder.detect_desync()

    # TODO: Detect desync
    # TODO: Get screenshots