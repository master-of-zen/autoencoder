#!/usr/bin/env python3

from distutils.spawn import find_executable
import sys
import re
import vapoursynth as vs
from pathlib import Path
from subprocess import Popen
import subprocess
import json
from pprint import PrettyPrinter

import os
import shlex
import pip

try:
    import argparse
except ImportError:
    print("Argparse not installed, installing..")
    pip.main(['install', '--user', 'argparse'])
    import argparse

try:
    from scipy import interpolate
except ImportError:
    print("Scipy not installed, installing..")
    pip.main(['install', '--user', 'scipy'])
    from scipy import interpolate


try:
    import numpy as np
except ImportError:
    print("Numpy not installed, installing..")
    pip.main(['install', '--user', 'numpy'])
    import numpy as np


try:
    import vapoursynth as vs
except ImportError:
    print("Vapoursynth not installed, installing..")
    pip.main(['install', '--user', 'vapoursynth'])
    import vapoursynth as vs


pp = PrettyPrinter(indent=2).pprint


class Autoencoder:
    def __init__(self):
        self.args = None
        self.input = None
        self.output = None
        self.tracks = None
        self.frames = None
        self.screenshots = None
        self.queue = None
        self.audio_tracks = []
        self.subtitle_tracks = []
        self.crop = ""
        self.ffmpeg_crop = ""
        self.desync_frames = 0
        self.tracks_info = None
        self.audio_tracks_names = []
        self.resolutions = None
        self.target_rate = None
        self.probe_frames = None
        self.match_crf = None

    def argparsing(self):
        """
        Command line parsing and setting default variables
        """
        parser = argparse.ArgumentParser()
        io_group = parser.add_argument_group("Input and Output")
        io_group.add_argument(
            "--input", "-i", type=Path, required=True, help="Input File/Folder"
        )
        io_group.add_argument("--output", "-o", type=Path,
                              help="Output file name")
        io_group.add_argument(
            "--screenshots",
            "-s",
            type=int,
            required=False,
            default=5,
            help="Number of screenshots to make",
        )
        io_group.add_argument(
            "--resolution", "-r", type=str, nargs="+", help="resolutions to encode in"
        )
        io_group.add_argument("--target_rate", type=int,
                              help="value of Kbps to target")
        io_group.add_argument("--probe_frames", type=int,
                              help="Probe size in frames")
        self.args = vars(parser.parse_args())
        self.input: Path = self.args["input"]
        if self.input.is_dir():
            self.queue = [x for x in self.input.iterdir() if x.is_file()]
        else:
            self.queue = [self.input]

        self.screenshots = self.args["screenshots"]

        if self.args["output"]:
            self.output = self.args["output"]
        else:
            self.output = Path(self.args["input"]).with_suffix(".mkv")

        if self.args["target_rate"]:
            self.target_rate = self.args["target_rate"]

        if self.args["probe_frames"]:
            assert self.args["probe_frames"] > 1
            self.probe_frames = self.args["probe_frames"]
        else:
            self.probe_frames = 500

    def check_executables(self):
        """Checking is all required executables reachable"""

        if not find_executable("ffmpeg"):
            print("No ffmpeg")
            sys.exit()

        if not find_executable("mkvextract"):
            print("Can't find mkvextract")
            sys.exit()
        if not find_executable("vspipe"):
            print("Can't find vspipe")
            sys.exit()

        if not find_executable("mediainfo"):
            print("Can't find mediainfo")
            sys.exit()

    def auto_crop(self):
        """Getting information about how source can be cropped"""

        script = f"ffmpeg -i {self.input.resolve()} -an -sn -vf fps=fps=5,cropdetect -t 240 -f null -".split()

        r = subprocess.run(script, capture_output=True)
        output = r.stderr.decode()

        c1, c2, crop_x, crop_y = [
            int(x)
            for x in re.findall(r"crop=([\d]+):([\d]+):([\d]+):([\d]+)", output)[-1]
        ]

        crop_left = crop_x
        crop_right = crop_x
        crop_top = crop_y
        crop_bottom = crop_y
        if crop_left + crop_right + crop_top + crop_bottom == 0 or crop_y < 16:
            print(":: No crop required")
        else:
            print(f":: Autocrop Detected")
            self.ffmpeg_crop = f"crop={c1}:{c2}:{crop_x}:{crop_y}"
            self.crop = f"video = core.std.Crop(video, left={crop_left}, right={crop_right},top = {crop_top},bottom = {crop_bottom})"

        return (crop_left, crop_right, crop_top, crop_bottom)

    def get_media_info(self):
        """
        Getting media info from input video
        Width, Height, Frames, Fps
        """
        if not self.input.exists():
            print(f"Video {self.input.resolve()} is not reachable")
            sys.exit()

        script = (
            "import vapoursynth as vs\n"
            + "core = vs.get_core()\n"
            + f"video = core.ffms2.Source(r'{self.input.resolve()}')\n"
            + "video.set_output()"
        )

        with open("get_media_info.py", "w") as fl:
            fl.write(script)
        print(":: Parsing source file..\r")
        r = subprocess.run(
            f"vspipe get_media_info.py -i -".split(), capture_output=True
        )
        output = r.stdout.decode()

        if len(r.stderr.decode()) > 0:
            print("Error in getting media info")
            print(r.stderr.decode())
            sys.exit()

        os.remove("get_media_info.py")

        self.w = int(re.findall("Width: ([0-9]+)", output)[0])
        self.h = int(re.findall("Height: ([0-9]+)", output)[0])
        self.frames = int(re.findall("Frames: ([0-9]+)", output)[0])

        self.fps = re.findall("([0-9]+[.]+[0-9]+) fps", output)[0]
        depth = int(re.findall("Bits: ([0-9]+)", output)[0])
        print(f":: Media info:\n:: {self.w}:{self.h} frames:{self.frames}\n")

    def extract(self):

        Path("Temp/Audio").mkdir(parents=True, exist_ok=True)

        audio = [x for x in self.tracks if x["@type"] == "Audio"]

        # pp(self.tracks)
        print(":: Extracting Audio")
        for x in audio:
            track = f'Temp/Audio/{x["StreamOrder"]}.mkv'
            self.audio_tracks.append(track)
            cmd = f'mkvextract -q {Path(self.input).resolve()} tracks {x["StreamOrder"]}:{track}'.split(
            )
            Popen(cmd).wait()

        print(":: Audio Extracted")

        Path("Temp/Subtitles").mkdir(parents=True, exist_ok=True)

        # pp(self.tracks)
        subtitles = [x for x in self.tracks if x["@type"] == "Text"]

        print(":: Extracting Subtitles")

        for x in subtitles:
            # print(x)
            track = f'Temp/Subtitles/{x["StreamOrder"]}.srt'
            self.audio_tracks.append(track)
            cmd = f'mkvextract -q {Path(self.input).resolve()} tracks {x["StreamOrder"]}:{track}'.split(
            )
            Popen(cmd).wait()

        print(":: Subtitles Extracted")

    def get_tracks_info(self):
        cmd = f"mediainfo --Output=JSON {self.input.resolve()}"
        r = subprocess.run(cmd.split(), capture_output=True)

        if len(r.stderr.decode()) > 0:
            print("Error in getting track info")
            print(r.stderr.decode())
            sys.exit()

        self.tracks = json.loads(r.stdout.decode())["media"]["track"]

        # pp(self.tracks)

    def merge(self):

        print(":: Mergin end result")

        # merge = [f'{x} --track_name {}' for ]

        # pp(self.tracks[1])

        audio = [x for x in self.tracks if x["@type"] == "Audio"]
        subtitles = [x for x in self.tracks if x["@type"] == "Text"]
        # print(audio, subtitles)

        # print(f' --track_name "{audio[0][1]}" Temp/Audio/{audio[0][0]}.mkv ')

        # Audio
        to_merge_audio = []
        for x in audio:
            track = x["StreamOrder"]

            # Handle title
            maybe_title = x.get("Title", "")
            if maybe_title:
                to_merge_audio.extend([f"--track-name", f'0:"{maybe_title}"'])

            # Handle language
            maybe_language = x.get("Language", "")
            if maybe_language:
                to_merge_audio.extend(["--language", f"0:{maybe_language}"])

            to_merge_audio.extend([f"Temp/Audio/{track}.mkv"])

        # Subtitles
        to_merge_subtitles = []
        for x in subtitles:
            track = x["StreamOrder"]

            # Handle title
            maybe_title = x.get("Title", "")
            if maybe_title:
                to_merge_subtitles.extend(
                    [f"--track-name", f'0:"{maybe_title}"'])

            # Handle language
            maybe_language = x.get("Language", "")
            if maybe_language:
                to_merge_subtitles.extend(
                    ["--language", f"0:{maybe_language}"])

            to_merge_subtitles.extend([f"Temp/Subtitles/{track}.srt"])

        to_merge = to_merge_audio + to_merge_subtitles

        cmd = [
            "mkvmerge",
            "-q",
            "--default-duration",
            f"0:{self.fps}fps",
            "Temp/encoded.mkv",
            "-o",
            self.output.resolve(),
            *to_merge,
        ]
        # print(cmd)

        Popen(cmd).wait()

    def detect_desync(self):
        """
        Detects desync beetween the original and encoded
        """

        print(":: Detecting desync")

        # Making source referense screenshot
        Path("Temp/Sync").mkdir(parents=True, exist_ok=True)
        cmd_source = (
            f"ffmpeg -y -loglevel warning -hide_banner -i {self.input} -an -sn -dn -filter_complex "
            + "'select=eq(n\\,1710)',"
            + f"{self.ffmpeg_crop} -frames:v 1 Temp/Sync/ref.png "
        )
        # print(cmd_source)

        Popen(shlex.split(cmd_source)).wait()

        # Making encoded screenshot
        cmd_enc = (
            f"ffmpeg -y -hide_banner -loglevel warning -i Temp/encoded.mkv -an -sn -dn -filter_complex "
            + "'select=between(n\\,1705\\,1715)',setpts=PTS-STARTPTS,"
            + f"{self.ffmpeg_crop}  Temp/Sync/%03d.png "
        )
        # print(cmd_enc)
        Popen(shlex.split(cmd_enc)).wait()
        # print(":: Encoded screenshots made")

        # r = subprocess.run(script, capture_output=True)
        # output = r.stderr.decode()

        # Sync frame is 6

        flist = []
        for p in Path("Temp/Sync").iterdir():
            if p.is_file() and "ref" not in p.name:
                # print(p)
                script = f"ffmpeg -hide_banner -i {p}  -i Temp/Sync/ref.png -filter_complex psnr -f null -"
                r = subprocess.run(shlex.split(script), capture_output=True)
                output = r.stderr.decode()
                # print(output)
                if "inf" in output:
                    score = 1000.0
                else:
                    score = float(re.findall(r"average:(\d+.\d+)", output)[-1])

                tp = (int(p.stem) - 6, score)
                flist.append(tp)
        self.desync_frames = max(flist, key=lambda x: x[1])[0]

        if self.desync_frames == 0:
            print(":: No desync detected")
        else:
            print(f":: Detected {self.desync_frames} desync")

    def encode(self):

        if self.w >= 1080:
            ref = 4
        elif self.w >= 720:
            ref = 9
        elif self.w >= 576:
            ref = 12
        elif self.w >= 480:
            ref = 16

        if self.match_crf:
            crf = self.match_crf
        else:
            crf = 20

        # Test
        """
        p2pformat = f'x264 --log-level error  --fps {self.fps} --preset superfast --demuxer y4m --output Temp/encoded.mkv - --crf 20 '
        """
        p2pformat = f"x264 --log-level error  --fps {self.fps} --preset veryslow --demuxer y4m --level 4.1 --b-adapt 2 --vbv-bufsize 78125 --vbv-maxrate 62500 --rc-lookahead 250  --me tesa --direct auto --subme 11 --trellis 2 --no-dct-decimate --no-fast-pskip --output Temp/encoded.mkv - --ref {ref} --min-keyint 24 --aq-mode 2  --qcomp 0.62 --psy-rd 30 --bframes 16 --crf {crf} --deblock -1:-1:-1"

        script = (
            "import vapoursynth as vs\n"
            + "core = vs.get_core()\n"
            + f"video = core.ffms2.Source(r'{self.input.resolve()}')\n"
            + self.crop
            + "\n"
            "video.set_output()"
        )

        settings_file = Path("settings.py")
        with open(settings_file, "w") as w:
            w.write(script)

        vs_pipe = f"vspipe --y4m {settings_file.resolve()} - "

        print(":: Encoding..\r")
        pr = Popen(vs_pipe.split(), stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)

        Popen(p2pformat.split(), stdin=pr.stdout).wait()

        print(":: Encoded")

    def make_screenshots(self):

        if self.screenshots == 0:
            return

        if self.desync_frames:
            print(f":: Making Screenshots with desync {self.desync_frames}")
        else:
            print(":: Making Screenshots")

        screenshot_places_source = np.linspace(
            0, self.frames, num=self.screenshots + 1, endpoint=False, dtype=int
        )[1:]

        screenshot_places_encoded = np.linspace(
            0 + self.desync_frames,
            self.frames + self.desync_frames,
            num=self.screenshots + 1,
            endpoint=False,
            dtype=int,
        )[1:]

        select_source = (
            f"'select=eq(n\\,{screenshot_places_source[0]})"
            + "".join([f"+eq(n\\,{x})" for x in screenshot_places_source[1:]])
            + "',"
        )

        Path("Screenshots").mkdir(parents=True, exist_ok=True)
        cmd_source = (
            f"ffmpeg -y -loglevel warning -hide_banner -i {self.input} -an -sn -dn -filter_complex "
            f"{select_source}"
            f"{self.ffmpeg_crop} -vsync 0 Screenshots/source_%d.png"
        )

        # print(cmd_source)
        cmd = shlex.split(cmd_source)
        # print(cmd)
        Popen(cmd).wait()

        select_encoded = (
            f"'select=eq(n\\,{screenshot_places_encoded[0]})"
            + "".join([f"+eq(n\\,{x})" for x in screenshot_places_encoded[1:]])
            + "',"
        )
        cmd_encode = (
            f"ffmpeg -y -loglevel warning -hide_banner -i {self.output} -an -sn -dn -filter_complex "
            + select_encoded
            + f"{self.ffmpeg_crop} -vsync 0 Screenshots/encoded_%d.png "
        )

        # print(cmd_encode)
        cmd_encoded = shlex.split(cmd_encode)
        # print(cmd_encoded)
        Popen(cmd_encoded).wait()
        print(":: Screenshot made")

    def match_rate(self):
        """Encoding a minute long segments a couple of times to find reasonable crf for encoding to match bitrates"""

        if self.w >= 1080:
            ref = 4
        elif self.w >= 720:
            ref = 9
        elif self.w >= 576:
            ref = 12
        elif self.w >= 480:
            ref = 16

        probe_path = Path("Temp/probe.mkv")

        try_settings = f"x264 --log-level error  --fps {self.fps} --preset veryslow --demuxer y4m --level 4.1 --b-adapt 2 --vbv-bufsize 78125 --vbv-maxrate 62500 --rc-lookahead 250  --me tesa --direct auto --subme 11 --trellis 2 --no-dct-decimate --no-fast-pskip --output Temp/probe.mkv - --ref {ref} --min-keyint 24 --aq-mode 2  --qcomp 0.62 --psy-rd 30 --bframes 16  --deblock -1:-1:-1"

        default_crf = "--crf 20"
        settings_file = Path("settings.py")
        vs_pipe = f"vspipe --y4m -s 2880 -e {2880 + self.probe_frames} {settings_file.resolve()} - "

        crf = 20
        probe_crfs = []  # (crf, rate)

        print(":: Matching rate..")

        for probe_num in range(1, 5):
            print(f":: Encoding.. Probe: {probe_num}\r")

            settings = try_settings + f" --crf {crf} "
            pr = Popen(vs_pipe.split(), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)

            Popen(settings.split(), stdin=pr.stdout).wait()

            cmd = f"mediainfo --Output=JSON {probe_path}"
            r = subprocess.run(cmd.split(), capture_output=True)

            if len(r.stderr.decode()) > 0:
                print("Error in getting track info")
                print(r.stderr.decode())
                sys.exit()

            bitrate = int(json.loads(r.stdout.decode())[
                          "media"]["track"][1]["BitRate"]) // 1000

            print(f"CRF: {crf} BitRate: {bitrate} Kbps")
            probe_crfs.append((crf, bitrate))

            # Checking rate
            if abs(bitrate - self.target_rate) < (self.target_rate // 10):
                print(f"Found crf: {crf}")
                self.match_crf = crf
                return

            if probe_num == 1:
                if bitrate > self.target_rate:
                    crf += 5
                else:
                    crf -= 5

            elif min([x[1] for x in probe_crfs]) < self.target_rate < max([x[1] for x in probe_crfs]):
                # Interpolate
                x = [x[0] for x in sorted(probe_crfs)]
                y = [x[1] for x in sorted(probe_crfs)]

                f = interpolate.interp1d(x, y, kind="linear")
                xnew = np.linspace(min(x), max(x), max(x) - min(x))
                tl = list(zip(xnew, f(xnew)))
                tpls = min(tl, key=lambda l: abs(l[1] - self.target_rate))
                crf = round(tpls[0], 1)

            else:
                # If we still can't match rate, extend the fork
                if self.target_rate > max([x[1] for x in probe_crfs]):
                    print(f"Print extending crf search: {crf} -> {crf - 5}")
                    crf -= 5
                elif self.target_rate < min([x[1] for x in probe_crfs]):
                    print(f"Print extending crf search: {crf} -> {crf + 5}")
                    crf += 5

        print(f"Closest CRF to match bitrate: {crf}")
        self.match_crf = crf


if __name__ == "__main__":
    encoder = Autoencoder()
    # Check initial requirements
    encoder.argparsing()
    encoder.check_executables()
    encoder.get_media_info()
    encoder.auto_crop()
    encoder.get_tracks_info()
    encoder.extract()
    # encdoer.encode_queue()
    if encoder.target_rate:
        encoder.match_rate()
    encoder.encode()
    encoder.merge()
    encoder.detect_desync()
    encoder.make_screenshots()
    print(":: All done!")
