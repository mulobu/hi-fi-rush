#!/usr/bin/env python3
"""
obs-setup -- build (or repair) this overlay's OBS scene collection.

Everything the overlay needs on the OBS side is derivable: one host scene
called COMIC holding the video sources plus three browser sources (the
overlay, the mascot, and the chat TTS player), a browser window that can
stand in for the game, Discord's audio, and six
trigger scenes that contain nothing but a nested reference to COMIC. This
script asserts that shape over obs-websocket, so moving to another machine is
"install OBS, enable the websocket, run this" rather than forty minutes of
clicking. See CLAUDE.md §2 for why the shape is what it is.

    python3 tools/obs-setup.py --check          report, change nothing
    python3 tools/obs-setup.py                  create and repair
    python3 tools/obs-setup.py --placeholders   colour blocks, no hardware
    python3 tools/obs-setup.py --prune          also remove strays from COMIC
    python3 tools/obs-setup.py --export         write obs/comic-scenes.json
    python3 tools/obs-setup.py --vertical       also build VCOMIC on the
                                                vertical canvas
    python3 tools/obs-setup.py --encoder auto   pick the best hardware encoder
                                                OBS reports on this machine

Canvas, delay, replay buffer and encoder live in the OBS *profile*, not the
collection, and every profile is checked, not only the active one: each is
switched to in turn and the one you were on is put back. A profile here is a
Restream setup -- see do_profiles. Never while anything is live.

Standard library only -- no pip install. The obs-websocket client below is
about eighty lines because a dependency you have to explain in a README is
worse than eighty lines you can read.

It is idempotent and conservative: it creates what is missing and repositions
what is misplaced, but it never deletes a source or overwrites one that exists
with a different kind. Those are reported for you to decide about, because a
script that silently replaces your webcam source is a script that eventually
eats a working setup.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CANVAS_W, CANVAS_H = 1920, 1080

HOST_SCENE = "COMIC"

# Scene name -> the panel it pans to. Must match SCENE_MAP in overlay.html.
TRIGGERS = ["START", "CHAT", "GAME", "CAM", "BRB", "END"]

# Bottom to top. The video sources sit under the overlay so its art can mask
# their spill; the mascot sits over it, because a mascot punched through as a
# hole would be a transparent rectangle instead of a sprite on comic art.
MASCOT_PORT = 4460

# chat/chat-bridge.py serves chat/tts.html here. Must match TTS_PORT there.
TTS_PORT = 4461

# --- vertical canvas -------------------------------------------------------
# A second 1080x1920 canvas, added by the Aitum Vertical Canvas plugin, which
# builds on OBS 32's native canvas API rather than running its own -- which is
# why the standard websocket requests can see into it at all.
#
# Measured on OBS 32.2.2 / obs-websocket 5.7.4: CreateScene, CreateSceneItem,
# SetSceneItemIndex and SetSceneItemTransform all work there, but ONLY by uuid.
# canvasName is silently ignored -- GetSceneList {canvasName: "Aitum Vertical"}
# hands back Main's scene list with no error -- and vertical scenes cannot be
# addressed by sceneName at all, because name lookup resolves within Main only.
# The uuid is random per scene collection, so it is discovered every run and
# never written down. See CLAUDE.md §2.
VERT_W, VERT_H = 1080, 1920

# Not COMIC: OBS shares one source namespace across canvases too, and a scene
# is a source internally.
VERT_SCENE = "VCOMIC"

# Bottom to top. The same inputs COMIC uses -- one input referenced from both
# canvases, with independent scene items, so the horizontal and vertical
# overlays cannot fight over a transform. No trigger scenes here: the vertical
# canvas needs exactly one scene and never switches, because vertical.html
# reads the MAIN canvas's program scene to decide where to pan.
#
# DeerV is last for the same reason Deer is last in COMIC: above the overlay,
# because a punched hole is a transparent rectangle and would put live video
# behind the mascot's own alpha instead of comic art.
VERT_STACK = ["Game", "Browser", "Cam", "Chat", "OverlayV", "DeerV"]
VERT_MANAGED = set(VERT_STACK)


# --- encoders --------------------------------------------------------------
# The pan is a CSS transform on a 7680x4320 page inside CEF, and Source Record
# adds an output per source on top of the program encode. The CPU has enough to
# do; the encode belongs on the GPU. CLAUDE.md §6 already names encoder count as
# the real ceiling.
#
# Only the encoder ID is asserted here, never bitrate, preset or tuning. Those
# live in the profile's streamEncoder.json / recordEncoder.json, which no
# websocket request can reach -- and they are a judgement call about your
# upload and your GPU, which a repo has no business making for you.

# Pre-OBS-30 IDs. OBS still accepts each one and silently maps it to the value
# on the right, logging "Encoder ID 'x' is deprecated and may be removed in a
# future version" once per output per launch. Rewriting them is a rename, not a
# change of encoder, which is why it happens on an ordinary run.
DEPRECATED_ENCODERS = {
    "jim_nvenc": "obs_nvenc_h264_tex",
    "jim_hevc_nvenc": "obs_nvenc_hevc_tex",
    "jim_av1_nvenc": "obs_nvenc_av1_tex",
    "ffmpeg_nvenc": "obs_nvenc_h264_tex",
    "obs_qsv11": "obs_qsv11_v2",
}

# Best first, for --encoder auto. H.264 only: YouTube and Twitch both take it
# everywhere, and an HEVC or AV1 ingest is a decision about your service, not
# about this overlay.
HW_PREFERENCE = [
    "obs_nvenc_h264_tex",   # NVIDIA
    "obs_qsv11_v2",         # Intel QuickSync
    "h264_texture_amf",     # AMD
    "com.apple.videotoolbox.videoencoder.ave.avc",
    "obs_x264",             # software, and the OBS default
]

# Simple output mode stores a short token instead of the encoder ID.
SIMPLE_TOKEN = {
    "obs_nvenc_h264_tex": "nvenc",
    "obs_qsv11_v2": "qsv",
    "h264_texture_amf": "amd",
    "com.apple.videotoolbox.videoencoder.ave.avc": "apple_h264",
    "obs_x264": "x264",
}
SIMPLE_ID = {v: k for k, v in SIMPLE_TOKEN.items()}
# Simple mode's own deprecated spellings.
SIMPLE_ID.update({"jim_nvenc": "obs_nvenc_h264_tex", "nvenc": "obs_nvenc_h264_tex",
                  "amd_h264": "h264_texture_amf"})

SOFTWARE_ENCODERS = {"obs_x264", "ffmpeg_svt_av1", "ffmpeg_aom_av1"}

# What --encoder accepts. "auto" is the first entry of HW_PREFERENCE this
# machine actually has.
ENCODER_CHOICES = {
    "nvenc": "obs_nvenc_h264_tex",
    "qsv": "obs_qsv11_v2",
    "amd": "h264_texture_amf",
    "apple": "com.apple.videotoolbox.videoencoder.ave.avc",
    "x264": "obs_x264",
}


def stack(placeholders: bool):
    """The COMIC scene, bottom item first."""
    video = "color_source_v3" if placeholders else None
    win = sys.platform.startswith("win")
    return [
        # name        real kind                              placeholder colour
        # Tts draws nothing and is parked off-canvas (do_tts); it is in COMIC
        # only because a source has to be in the live scene for its audio to
        # reach the mix. Bottom, so it is under everything if it ever drew.
        ("Tts", "browser_source", None),
        ("Game", video or ("game_capture" if win else "screen_capture"), 0xFF10DA16),
        # Directly above Game, whose hole it borrows while it is on air; under
        # Cam, whose window sits inside the game panel. See BROWSER_SOURCE.
        ("Browser", video or ("window_capture" if win else "screen_capture"), 0xFFE0A030),
        ("Cam", video or ("dshow_input" if win else "av_capture_input_v2"), 0xFF3C8BDA),
        ("Chat", video or "browser_source", 0xFFDA2624),
        ("Overlay", "browser_source", None),
        ("Deer", "browser_source", None),
    ]


# Sources that belong in COMIC. The overlay positions Game, Browser, Cam and
# Chat through obs-websocket; Deer positions itself, Tts is parked by this
# script, and Discord is audio only. Anything else in COMIC is a stray as far
# as this script is concerned.
MANAGED = {"Game", "Browser", "Cam", "Chat", "Overlay", "Deer", "Tts", "Discord"}


# Chat TTS. The bridge synthesises each line with Piper and the Tts browser
# source plays it, so speech enters OBS on its own fader -- the deck can mute
# TTS without muting alerts, which ride Overlay. See CLAUDE.md "Chat TTS".
#
# Parked off-canvas like the overlay's unused sources: it is transparent and
# draws nothing, but nothing else positions it, and a stray rectangle at 0,0
# would sit inside START's webcam window the day the page grew a debug panel.
TTS_SOURCE = "Tts"
# Monitor AND output: on stream, and in your ears. The monitor plays from
# obs64.exe, and every capture left in this setup is of one application (see
# do_audio), so nothing can pick the monitored line up a second time. That was
# measured safe even back when Desktop Audio captured the whole endpoint: OBS
# 32 dedups monitored sources out of an output capture on the same device.
TTS_MONITOR = "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT"


# The browser, shown in place of the game without a scene of its own.
#
# `Browser` is a window capture with no hole in either overlay. While it is
# UNMUTED, overlay.html and vertical.html put it wherever `Game` would have
# gone and park Game instead; muted, it is parked and the game is back. Mute
# is the switch because it already is one for the audio -- the page goes on
# air with its sound and comes off with it -- and because both the deck and
# OBS's own mixer can flip it with state that reads back. The overlays treat
# "unknown" as muted, so the browser never goes on air on a guess.
#
# Created muted and parked off-canvas, in that order before it is anything
# else, because a fresh capture sits at 0,0 above Game until an overlay moves
# it. After creation the window, method and mute are yours: pick another
# window in its properties and a setup run leaves it there. Only Capture
# Audio is asserted, by do_audio, because that one decides whether a sound
# reaches the stream twice.
#
# Windows Graphics Capture (method 2), because Chrome draws on the GPU and
# BitBlt captures it as black. Priority 2 matches the title first and then
# any window of the same executable, so a tab change never loses it.
BROWSER_SOURCE = "Browser"
BROWSER_SETTINGS = {
    "window": "Google Chrome:Chrome_WidgetWin_1:chrome.exe",
    "priority": 2,
    "method": 2,
    "client_area": True,
    "cursor": True,
    "capture_audio": False,         # do_audio turns it on once nothing doubles it
}
PARK = {"positionX": float(CANVAS_W + 200), "positionY": float(CANVAS_H + 200)}
VERT_PARK = {"positionX": float(VERT_W + 200), "positionY": float(VERT_H + 200)}


# The deck's camera kill switch, asserted on the Cam *input*.
#
# A filter belongs to the input, never to a scene item, so one filter covers
# every canvas referencing Cam -- COMIC and VCOMIC both, from a single toggle.
# Hiding the scene item cannot do that twice over: items are independent per
# canvas, and obs-websocket resolves a vertical scene only by sceneUuid, which
# a deck addressing sources by name can never reach.
#
# It also survives a pan, which a hidden item does not -- syncVisibility in
# overlay.html and vertical.html both re-enable a managed item they find
# disabled on the next scene change. Neither page touches filters.
#
# color_multiply 0 is black, so every pixel multiplies to opaque black. Not
# opacity 0: that makes the hole transparent and reveals whatever sits below
# Cam in the stack, which in COMIC is Game.
CAM_OFF_SOURCE = "Cam"
CAM_OFF_FILTER = "CAM OFF"
CAM_OFF_KIND = "color_filter_v2"
CAM_OFF_SETTINGS = {"color_multiply": 0}


# The camera grade, asserted on the same Cam input and deliberately ABOVE the
# kill switch -- but only with --grade. Off by default since 2026-10-17, when
# it was taken off the camera: without the flag this script neither adds a
# GRADE filter nor removes one, so a grade added by hand is left alone too.
#
# Order is the load-bearing part here, not presence. CAM OFF multiplies every
# pixel by zero to get opaque black; this LUT lifts the black point off zero,
# because a faded toe is half of what the look is. Put the grade second and the
# kill switch stops killing -- black goes in, 0.020 0.070 0.090 comes out, and
# the camera reads as a dim teal rectangle rather than off. So GRADE is pinned
# to index 0 and CAM OFF follows it.
#
# Being a filter on the *input* it crosses canvases and survives a pan, for the
# same two reasons CAM OFF does.
#
# Two things are deliberately NOT asserted after creation, the way CAM OFF's
# enabled state is not:
#   - `clut_amount` is the taste dial. It blends the table against the raw
#     image live, which is how the look softens without regenerating anything.
#     SetSourceFilterSettings merges by default, so writing image_path alone
#     leaves it where you left it.
#   - `image_path` is taken as given as long as it names a file that exists
#     inside assets/luts, so choosing kolder-strong.cube by hand survives a
#     setup run. Only a path that is missing or outside that directory is
#     repaired.
GRADE_FILTER = "GRADE"
GRADE_KIND = "clut_filter"
GRADE_LUT_DIR = REPO / "assets/luts"
GRADE_LUT = GRADE_LUT_DIR / "kolder.cube"
GRADE_GENERATOR = REPO / "tools/cam-grade.py"


# Audio: one application per capture, and nothing capturing a whole device.
#
# The game comes from Game Capture's own "Capture Audio", Discord from an
# Application Audio Capture, the browser from its window capture's "Capture
# Audio". All three ride Windows' process loopback, which takes one process
# tree's sound whichever endpoint it plays to -- so notifications, music and
# anything else on the PC stay off stream, and Windows moving the default
# output between the speakers and the monitor's HDMI no longer touches the
# stream at all. That move used to restart Desktop Audio mid-stream; the log
# of 2026-10-25 has it switching endpoint twice in 25 minutes.
#
# Game's audio follows whatever window Game hooks, so a new game needs
# picking in one place, not two.
#
# Desktop Audio has to go first, and the order is the load-bearing part.
# It captures the whole output, which already holds the game, the browser
# and Discord, so any per-app capture next to it sums the same sound twice
# from two independent clocks: a comb filter whose notches sweep as the
# offset drifts, which sounds like the game vibrating underwater rather than
# like a duplicate. Measured when Game's Capture Audio was once ticked beside
# it, mid-stream. So while any output capture exists this script keeps every
# Capture Audio off and adds no Discord capture, and says so.
#
# Desktop Audio is a global audio device, and the websocket cannot disable
# one. OBS's own "Disabled" takes the source off its output channel, which no
# request does -- RemoveInput is not the same thing, and what it leaves
# behind on a channel is not something to find out mid-stream. It is one
# dropdown for you: Settings -> Audio -> Global Audio Devices -> Desktop
# Audio -> Disabled.
#
# Mute is deliberately NOT asserted. It is a live toggle the deck owns, the
# same way it owns CAM OFF's enabled state.
GAME_SOURCE = "Game"
OUTPUT_CAPTURE_KINDS = ("wasapi_output_capture",)

# Discord: its voice plays from Discord.exe's own process tree, which is what
# process loopback captures. Priority 2 matches the title first and then any
# window of Discord.exe, because the title follows whichever channel is open.
# It must sit in COMIC like Tts -- a source reaches the mix only from a scene
# that is on air -- and draws nothing, so nothing positions it.
DISCORD_SOURCE = "Discord"
DISCORD_KIND = "wasapi_process_output_capture"
DISCORD_SETTINGS = {"window": "Discord:Chrome_WidgetWin_1:Discord.exe", "priority": 2}


# The microphone denoiser, asserted on whatever input is the mic: NVIDIA Noise
# Removal where this machine can run it, RNNoise where it cannot -- but only
# with --denoise. Opt-in since 2026-10-29: viewers reported the voice breaking
# up, and NV DENOISE was at both of its most aggressive settings (intensity
# 1.0, VAD on), where a syllable the model misreads goes to digital silence
# rather than getting quieter. It was taken off and put back the same evening
# at 0.7 with VAD off, which is what --denoise now creates. Without the flag
# this script neither adds a denoiser nor removes one, the way --grade treats
# GRADE. Everything below holds whenever it is on.
#
# NVIDIA, because the noise that matters here is the keyboard and the mouse.
# RNNoise is built for steady noise -- fan, hum, room -- and lets short clicks
# through. Measured 2026-10-25 on the USB Condenser Microphone: clicks left it
# at -36 to -22 dBFS, the same range as the voice, so nothing downstream that
# decides by level can tell them apart. Over 40 s of typing, alternating the two
# every 2 s, frames above -60 went 139 -> 62 and the loudest 0.1 -> -15.6 dBFS.
# Better, not silent. That was at intensity 1.0 with `vad` on -- NVIDIA's own
# voice detection, which quiets the gaps between words and is also what sends
# a misread syllable to silence. 0.7 with VAD off lets a little more keyboard
# through; not yet measured. It runs on the GPU, so it costs the game a little
# rather than costing CEF's CPU -- and it dies with the GPU: a driver reset
# leaves it logging "Denoiser run failed" every frame until OBS restarts.
#
# It cannot be created on a machine without it. OBS registers
# nvidia_audiofx_filter only when NVIDIA's Audio Effects SDK redistributable for
# that GPU is installed -- an RTX card, Windows, a download from NVIDIA's
# Broadcast page and an OBS restart -- and no request installs it. So the kind
# list decides: present, NV DENOISE is the denoiser; absent, DENOISE is.
#
# NV DENOISE's settings are written at creation and then left alone as taste,
# the way the ducks' are -- except a method that removes no noise at all.
# `dereverb` alone takes out room echo and leaves the keyboard, which reads as
# the filter silently failing.
#
# RNNoise, not Speex, for the fallback. Speex subtracts a fixed noise profile
# and gets robotic as you push it; RNNoise is a small recurrent net trained on
# speech-plus-noise, which is what makes it hold a voice together while it takes
# out fan hum and room. It costs more CPU, and that is a real cost here -- CEF
# is already carrying a 7680x4320 transform -- but it is a fraction of one core
# against a browser source doing compositing.
#
# `suppress_level` is deliberately not set: it is the Speex slider and RNNoise
# ignores it entirely. There is nothing to tune on the RNNoise path, which is
# the other half of why it is the right default for a script to assert.
#
# Method is asserted, never assumed. v2's default IS rnnoise, but only where
# librnnoise was compiled in; v1's default is speex. Writing it explicitly
# costs nothing and removes the build from the answer.
#
# A hand-set `speex` is left alone, the way a hand-picked LUT is (above). It is
# the documented fallback for a machine that cannot carry RNNoise, so it is a
# choice, not a fault. Only a method that is neither gets repaired.
#
# Exactly one of the two should be on: two denoisers in a row thin the voice,
# each taking a little more of what the other left. Enabled state is still the
# user's, with two exceptions where this script is only finishing its own move.
# Creating NV DENOISE switches an enabled DENOISE off, since it is the
# replacement. And an NV DENOISE that cannot run -- the SDK uninstalled, the
# collection imported onto a machine with no RTX card -- loads as a filter that
# passes audio through untouched, so a DENOISE left off behind it is switched
# back on; that is what a fallback is for.
MIC_SOURCE = "Mic/Aux"
MIC_KINDS = ("wasapi_input_capture", "coreaudio_input_capture")
NV_DENOISE_FILTER = "NV DENOISE"
NV_DENOISE_KIND = "nvidia_audiofx_filter"
NV_DENOISE_SETTINGS = {"method": "denoiser", "intensity": 0.7, "vad": False}
NV_DENOISE_METHODS = ("denoiser", "dereverb_denoiser")   # the ones that denoise
DENOISE_FILTER = "DENOISE"
DENOISE_KIND = "noise_suppress_filter_v2"
DENOISE_SETTINGS = {"method": "rnnoise"}

# The mic chain, since 2026-10-29: EQ, then a compressor, then a limiter -- the
# order the streaming guides converge on once noise suppression is set aside.
# Reddit itself was out of reach of the research tools; the guides say the same.
#
# EQ is OBS's 3-Band EQ with the high band turned down. OBS has no low-pass
# filter, and this is the nearest it ships: a shelf, not a steep cut, so the
# top end softens without the consonants going. A true low-pass (or the 80-100
# Hz high-pass the guides also want) needs a VST such as ReaEQ, loaded through
# vst_filter the way VOICE GATE was.
#
# COMPRESS is 3:1 from -18, 6 / 60 ms, +4 makeup -- the guides' starting point
# with a small makeup on purpose. With no denoiser above it, makeup lifts the
# keyboard and the room exactly as much as the voice; that is what -36 / 4:1 /
# +20 did over RNNoise, clicks near -42 coming out near -22, as loud as speech.
#
# No gate: it is the classic cause of clipped word endings, and an expander
# (-50 RMS, 3:1, 5 / 200 ms) changed nothing measurable against typing.
#
# Settings are written at creation and then left alone -- the EQ's high band
# is the dial for how soft the voice sounds. Order is asserted on every run:
# these three sit at the bottom of the chain in this order, LIMIT last, because
# anything after a limiter can push past its ceiling and the ducks read the
# very end of this chain. A COMPRESS from before 2026-10-29 keeps whatever
# settings it has; only its position is asserted.
MIC_DYNAMICS = [
    ("EQ", "basic_eq_filter", {"low": 0.0, "mid": 0.0, "high": -6.0}),
    ("COMPRESS", "compressor_filter",
     {"ratio": 3.0, "threshold": -18.0, "attack_time": 6, "release_time": 60,
      "output_gain": 4.0, "sidechain_source": "none"}),
    ("LIMIT", "limiter_filter", {"threshold": -3.0, "release_time": 60}),
]

# Ducking: sidechain compressors on the things you talk over, so they drop
# while you speak. A sidechain reads its key at the END of the key's filter
# chain -- after the denoiser, so keyboard and fan never dip the game.
#
# 3:1 from -38, attack 50 ms, release 1000 ms. Fitted 2026-10-25 to a take
# through NV DENOISE, run through OBS's own sidechain envelope (peak, one-pole
# attack and release): a median 11 dB duck while you talk, mostly 6 to 15,
# 22 at a shout; isolated clicks leave the game alone at the median and dip it
# about 5 dB at the loudest tenth. The voice swings 24 dB between phrases there
# (run peaks -27 to -3), and with no compressor to hold it the ratio is what
# keeps the game from swinging with it: depth is the key's excess over the
# threshold times (1 - 1/ratio), so 3:1 passes two thirds of the swing where
# 32:1 passed all of it -- a 28 dB hole at a shout, 3 dB under a quiet phrase.
# Gentler ratios are steadier still but let more clicks through: 2:1 dipped the
# game on clicks a third deeper. The slow attack is for clicks too. A click is
# ~10 ms, so a 50 ms attack lets its envelope rise a fifth of the way, while
# speech lasts long enough to reach full depth ~50 ms late, which is nothing
# against a game. Modelled from 12 s of speech and 22 clicks -- a short take,
# so worth a second one over a real game. Release 1000 ms holds the duck
# across the short gaps between words and has the game back within about
# 1.5 s of you stopping. The old 32:1 from -24 was tuned against COMPRESS's
# +20 and gave a median 3.5 dB once it was off.
#
# That a duck reaches Game Capture's audio at all is measured: in an earlier
# take the game's level fell with the modelled duck -- -35, -45, -55 dB RMS at
# none, 1-6 and 6+ dB.
#
# The game also ducks under Discord, lighter -- 3:1, about 8 dB under a friend
# at normal volume -- so callouts carry over the game. Discord itself never
# ducks: dipping your friends every time you speak makes talking over each
# other unintelligible. Alerts ride Overlay and TTS rides Tts; neither ducks.
#
# The voice duck was fitted to the 2026-10-25 chain -- NV DENOISE, no
# compressor. Since 2026-10-29 the key carries no denoiser and a +4 dB
# compressor, so clicks reach the sidechain louder and the voice swings less:
# expect the game to dip on typing until it is refitted.
#
# Only the sidechain is asserted after creation. Threshold, attack and release
# are taste, tuned by ear, and a setup run must not undo that.
DUCK_KIND = "compressor_filter"
DUCK_VOICE = {"ratio": 3.0, "threshold": -38.0, "attack_time": 50,
              "release_time": 1000, "output_gain": 0.0}
DUCK_FRIENDS = {"ratio": 3.0, "threshold": -24.0, "attack_time": 10,
                "release_time": 600, "output_gain": 0.0}
MIC_KEY = None                      # whichever input find_mic settles on
DUCKS = [
    # target          filter          keyed off        settings at creation
    (GAME_SOURCE,     "DUCK",         MIC_KEY,         DUCK_VOICE),
    (GAME_SOURCE,     "DUCK DISCORD", DISCORD_SOURCE,  DUCK_FRIENDS),
    (BROWSER_SOURCE,  "DUCK",         MIC_KEY,         DUCK_VOICE),
]



# Clips are timestamps. The deck's clip button runs `--clip`, which appends a
# row to clip_marks() and nothing else; the moment is cut later from the VOD or
# Restream's recording. There is no replay buffer, so nothing sits in RAM
# waiting for a press that may never come.
#
# `RecRB` lives per output mode and only the active one is read, so the
# inactive section is a landmine: a buffer left enabled there comes back the
# day the mode is switched. Both are asserted off.
CLIP_PATH = "C:/Users/Deep/Videos/Stream Clips"


def clip_marks(started: datetime) -> Path:
    """The marks file for a stream: clip-marks-YYYY-MM-DD.csv, by the day it
    *started*, not the day of the press. A stream crosses midnight -- the marks
    at 00:02 and 01:05 on 2026-10-24 belong to one started at 22:39 the
    evening before -- and one stream's marks belong in one file."""
    return Path(CLIP_PATH) / ("clip-marks-%s.csv" % started.strftime("%Y-%m-%d"))

# Stream delay, seconds. OBS holds the delayed stream in RAM as encoded
# packets -- about bitrate x delay, ~90 MB at 6 Mbps. 300 until 2026-10-27,
# when it was cut to 120 by hand in OBS and this followed.
#
# The vertical stream inherits this delay: with its advanced stream settings
# off, the plugin applies the main profile's Output/Delay* when it starts its
# own output. Only with them on does its own `stream_delay_*` take over.
STREAM_DELAY = 120

# The vertical plugin's websocket vendor. Restream's 1.2.0 answers on it;
# Aitum 1.6.4 did not (§2). `--go-live` starts the vertical stream through it
# at the same click as the main one, because the plugin's own Autostart waits
# for OBS's "streaming started" -- which a delay holds back until the countdown
# ends, so the vertical would go live a whole delay late.
VERT_VENDOR = "aitum-vertical-canvas"


# The chat hole is punched, so the widget's own page is what shows through it.
# A transparent chat box therefore reads as a black rectangle cut out of the
# panel, not as chat floating on comic art -- hence the opaque --peri ground,
# which is the chat panel's own background colour.
#
# The rest strips YouTube's popout chrome, measured against a live
# youtube.com/live_chat?v=...&is_popout=1 page: #panel-pages is the "Sign in to
# chat" footer, #show-more the jump-to-latest pill. With the header and footer
# hidden the message list reflows to the full height on its own. The selectors
# are inert for any other provider, so this is safe to leave set.
CHAT_CSS = """\
body { background: #b9c3d6 !important; margin: 0; overflow: hidden; }
yt-live-chat-header-renderer, #panel-pages, #show-more,
yt-live-chat-banner-manager { display: none !important; }
yt-live-chat-renderer, #chat, #contents, #item-list, #item-scroller, #items,
yt-live-chat-item-list-renderer { background: transparent !important; }
#item-scroller { overflow: hidden !important; }
yt-live-chat-text-message-renderer { font-size: 20px !important; padding: 5px 10px !important; }
yt-live-chat-text-message-renderer #author-name { color: #16161d !important; font-weight: 700 !important; }
yt-live-chat-text-message-renderer #message { color: #16161d !important; }"""


# ---------------------------------------------------------------------------
# a very small websocket client


class WS:
    """Text-frame websocket client. Enough for obs-websocket v5, no more."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                "GET / HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise ConnectionError("server closed during handshake")
            head += chunk
        if b"101" not in head.split(b"\r\n")[0]:
            raise ConnectionError("handshake refused: %s" % head.split(b"\r\n")[0])
        self.buf = b""

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("server closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj) -> None:
        payload = json.dumps(obj).encode()
        n = len(payload)
        header = bytearray([0x81])  # FIN + text
        if n < 126:
            header.append(0x80 | n)
        elif n < 1 << 16:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(
            bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        )

    def recv(self):
        while True:
            b0, b1 = self._recv_exact(2)
            opcode = b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            data = self._recv_exact(n) if n else b""
            if opcode == 0x9:  # ping
                self.sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                continue
            if opcode == 0x8:  # close
                raise ConnectionError("server closed the socket")
            if opcode in (0x1, 0x2):
                return json.loads(data)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


class OBS:
    def __init__(self, host: str, port: int, password: str) -> None:
        self.ws = WS(host, port)
        hello = self.ws.recv()
        d = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = hello["d"].get("authentication")
        if auth:
            if not password:
                raise SystemExit(
                    "error: this obs-websocket wants a password and none was found.\n"
                    "       pass --password, set OBS_WS_PASSWORD, or let the script\n"
                    "       read it from OBS's own config (see --help)."
                )
            secret = base64.b64encode(
                hashlib.sha256((password + auth["salt"]).encode()).digest()
            ).decode()
            d["authentication"] = base64.b64encode(
                hashlib.sha256((secret + auth["challenge"]).encode()).digest()
            ).decode()
        self.ws.send({"op": 1, "d": d})
        got = self.ws.recv()
        if got.get("op") != 2:
            raise SystemExit("error: obs-websocket refused the password")
        self.n = 0
        self.config_events = False

    def req(self, kind: str, data=None):
        self.n += 1
        rid = "s%d" % self.n
        self.ws.send(
            {"op": 6, "d": {"requestType": kind, "requestId": rid,
                            "requestData": data or {}}}
        )
        while True:
            m = self.ws.recv()
            if m.get("op") == 7 and m["d"]["requestId"] == rid:
                st = m["d"]["requestStatus"]
                if not st["result"]:
                    raise ObsError(kind, st.get("comment") or st.get("code"))
                return m["d"].get("responseData") or {}

    def switch_profile(self, name: str) -> None:
        """SetCurrentProfile, returning only once OBS has finished the switch.

        The request answers before the switch has happened -- RemoveProfile's
        own GetProfileList straight after it still listed the removed profile
        -- and a switch resets video and rebuilds every output, so a parameter
        read mid-switch could come from either profile. OBS fires
        CurrentProfileChanged at the very end, so that is what is waited on.
        """
        if self.req("GetProfileList")["currentProfileName"] == name:
            return
        if not self.config_events:
            # Reidentify: the Config category carries the profile events. req()
            # skips events, so leaving it on costs nothing afterwards.
            self.ws.send({"op": 3, "d": {"eventSubscriptions": 1 << 1}})
            while self.ws.recv().get("op") != 2:
                pass
            self.config_events = True
        self.n += 1
        rid = "s%d" % self.n
        self.ws.send(
            {"op": 6, "d": {"requestType": "SetCurrentProfile", "requestId": rid,
                            "requestData": {"profileName": name}}}
        )
        answered = switched = False
        while not (answered and switched):
            m = self.ws.recv()
            d = m.get("d") or {}
            if m.get("op") == 7 and d.get("requestId") == rid:
                st = d["requestStatus"]
                if not st["result"]:
                    raise ObsError("SetCurrentProfile",
                                   st.get("comment") or st.get("code"))
                answered = True
            elif (m.get("op") == 5 and d.get("eventType") == "CurrentProfileChanged"
                  and (d.get("eventData") or {}).get("profileName") == name):
                switched = True


class ObsError(RuntimeError):
    def __init__(self, kind, comment):
        super().__init__("%s failed: %s" % (kind, comment))


# ---------------------------------------------------------------------------
# password discovery


def obs_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/obs-studio"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", "")) / "obs-studio"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obs-studio"


def discover_password() -> str:
    """Read the password OBS generated for itself on this machine.

    The password is per-install, so it can never live in the repo. Reading it
    from OBS's own config is what makes `run the script` work on a new machine
    without the user hunting through Tools -> WebSocket Server Settings.
    """
    cfg = obs_config_dir() / "plugin_config/obs-websocket/config.json"
    try:
        return json.loads(cfg.read_text()).get("server_password", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# export


EXPORT_DEFAULT = REPO / "obs" / "comic-scenes.json"

# Query parameters and settings keys that carry a credential. Scrubbed by name
# rather than by value, so this never has to know what the secret actually is.
SECRET_PARAMS = {"pw", "password", "passwd", "key", "token", "auth", "secret"}
SECRET_KEYS = {"password", "server_password", "key", "stream_key", "token",
               "auth_token", "secret", "bearer_token"}

REPO_TOKEN = "{{REPO}}"
HOME_TOKEN = "{{HOME}}"


def collection_path(name: str = "") -> Path:
    """The scene collection OBS has on disk.

    OBS autosaves every few minutes and on a clean quit, so this can lag your
    last change. The caller reports the file's mtime for exactly that reason.
    """
    d = obs_config_dir() / "basic/scenes"
    files = sorted(p for p in d.glob("*.json") if p.suffix == ".json")
    if not files:
        raise SystemExit("error: no scene collection found in %s" % d)
    def display(f: Path) -> str:
        try:
            return json.loads(f.read_text()).get("name") or f.stem
        except Exception:
            return f.stem

    if name:
        # Either spelling. OBS's display name can hold spaces that the filename
        # replaces with underscores, and the listing below has to print one of
        # them -- so whatever it prints must also be accepted back.
        for f in files:
            if name in (display(f), f.stem):
                return f
        raise SystemExit(
            "error: no collection named %r in %s\n       have: %s"
            % (name, d, ", ".join(sorted({display(f) for f in files})))
        )
    if len(files) > 1:
        raise SystemExit(
            "error: %d collections in %s -- name the one you want with "
            "--collection\n       %s"
            % (len(files), d, ", ".join(sorted({display(f) for f in files})))
        )
    return files[0]


def scrub_url(url: str) -> str:
    """Drop credential query params, and tokenise anything machine-specific."""
    if not isinstance(url, str) or not url:
        return url
    parts = urllib.parse.urlsplit(url)
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in SECRET_PARAMS]
    url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path,
         urllib.parse.urlencode(kept), parts.fragment)
    )
    # file:// urls into this repo become a token. obs-setup.py rewrites them to
    # the real path on whatever machine imports the collection.
    repo_uri = REPO.as_uri()
    if url.startswith(repo_uri):
        url = REPO_TOKEN + url[len(repo_uri):]
    return url


def scrub(node):
    """Recursively strip secrets, repo paths and home paths."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k.lower() in SECRET_KEYS:
                out[k] = ""
            elif k == "url":
                out[k] = scrub_url(v)
            else:
                out[k] = scrub(v)
        return out
    if isinstance(node, list):
        return [scrub(v) for v in node]
    if isinstance(node, str):
        # Catches anything the structured rules missed -- module settings,
        # recording paths, script paths. Your username is not repo content.
        home = str(Path.home())
        for raw, token in ((REPO.as_uri(), REPO_TOKEN), (str(REPO), REPO_TOKEN),
                           (Path.home().as_uri(), HOME_TOKEN), (home, HOME_TOKEN)):
            node = node.replace(raw, token)
            node = node.replace(urllib.parse.quote(raw), token)
        return node
    return node


def live_shape(a):
    """The COMIC stack as OBS has it *right now*, or None if OBS is not up.

    Only used to catch a stale file. Export itself needs no websocket.
    """
    try:
        obs = OBS(a.host, a.port, a.password or discover_password())
    except Exception:
        return None
    try:
        scenes = {x["sceneName"] for x in obs.req("GetSceneList")["scenes"]}
        # Every canvas, not just Main. One scene collection file holds the
        # scenes of all of them -- a vertical canvas is a native libobs canvas,
        # so VCOMIC is written into the same JSON -- while GetSceneList without
        # a canvasUuid answers for Main alone. Compare those two and the file
        # looks permanently stale by exactly the vertical scenes, which is a
        # refusal to export that no amount of quitting OBS can clear.
        #
        # GetCanvasList is OBS 32 / obs-websocket 5.7; older builds have no
        # second canvas to miss.
        try:
            for c in obs.req("GetCanvasList")["canvases"]:
                if c.get("canvasFlags", {}).get("MAIN"):
                    continue
                scenes |= {x["sceneName"] for x in obs.req(
                    "GetSceneList", {"canvasUuid": c["canvasUuid"]})["scenes"]}
        except ObsError:
            pass
        items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
        stack_ = [i["sourceName"] for i in
                  sorted(items, key=lambda i: i["sceneItemIndex"])]
        return scenes, stack_
    except ObsError:
        return None
    finally:
        obs.ws.close()


def file_shape(doc):
    scenes = {x["name"] for x in doc.get("sources", []) if x.get("id") == "scene"}
    comic = next((x for x in doc.get("sources", [])
                  if x.get("name") == HOST_SCENE and x.get("id") == "scene"), None)
    stack_ = [i["name"] for i in comic.get("settings", {}).get("items", [])] if comic else []
    return scenes, stack_


def do_export(a) -> None:
    src = Path(a.export_from) if a.export_from else collection_path(a.collection)
    out = Path(a.out) if a.out else EXPORT_DEFAULT

    raw = json.loads(src.read_text())
    age = time.time() - src.stat().st_mtime

    # OBS keeps the collection in memory and writes it out on its own schedule,
    # so the file on disk can be minutes behind what you are looking at. An
    # export of a stale file is worse than no export -- it looks right and
    # ships the setup you already fixed. Compare against the live scene graph
    # and refuse rather than warn.
    if not a.export_from:
        live = live_shape(a)
        if live and live != file_shape(raw):
            ls, lstack = live
            fs, fstack = file_shape(raw)
            raise SystemExit(
                "error: %s is stale -- OBS has changes it has not written out yet.\n"
                "\n"
                "       on disk : %s\n"
                "       in OBS  : %s\n"
                "%s"
                "\n"
                "       Quit OBS (it saves on a clean exit) and run this again, or use\n"
                "       Scene Collection -> Export in OBS and pass --export-from <file>."
                % (
                    src.name,
                    " < ".join(fstack) or "(no %s scene)" % HOST_SCENE,
                    " < ".join(lstack) or "(no %s scene)" % HOST_SCENE,
                    ("       scenes  : on disk %s, in OBS %s\n"
                     % (sorted(fs), sorted(ls))) if fs != ls else "",
                )
            )

    clean = scrub(raw)

    # OBS names the imported collection after this field, and "Untitled" is a
    # poor thing to hand someone. Landing on START also beats importing into
    # whatever scene happened to be live when the file was written.
    clean["name"] = a.name
    if HOST_SCENE in [x.get("name") for x in clean.get("sources", [])]:
        clean["current_scene"] = "START"
        clean["current_program_scene"] = "START"

    # Belt and braces: never write a file that still looks like it holds a
    # credential. Structural scrubbing above should make this unreachable.
    blob = json.dumps(clean)
    leaks = [p for p in SECRET_PARAMS if ("%s=" % p) in blob and
             not blob.count("%s=&" % p) and not blob.count('%s="' % p)]
    if str(Path.home()) in blob:
        leaks.append("home path")
    if leaks:
        raise SystemExit(
            "error: refusing to write %s -- it still looks like it contains %s.\n"
            "       This is a bug in obs-setup.py; do not commit the file."
            % (out, ", ".join(sorted(set(leaks))))
        )

    unmanaged = sorted(
        {i["name"] for s2 in clean.get("sources", [])
         if s2.get("id") == "scene" and s2.get("name") == HOST_SCENE
         for i in s2.get("settings", {}).get("items", [])}
        - MANAGED
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")

    print("exported %s" % out)
    print("  from      %s" % src)
    print("  collection %r, %d scenes, %d sources"
          % (clean.get("name"), sum(1 for x in clean.get("sources", [])
                                    if x.get("id") == "scene"),
             sum(1 for x in clean.get("sources", [])
                 if x.get("id") != "scene")))
    print("  saved     %d min ago by OBS" % (age // 60))
    print("  scrubbed  credential query params, %s -> %s, home -> %s"
          % (REPO, REPO_TOKEN, HOME_TOKEN))

    if age > 300 and a.export_from:
        print("\n  ! that file is %d min old, and --export-from skips the staleness"
              % (age // 60))
        print("    check against the running OBS. Make sure it is the one you meant.")
    if unmanaged:
        print("\n  ! %s sits in %s but no hole maps to it, so this export bakes in a"
              % (", ".join(unmanaged), HOST_SCENE))
        print("    source that shows through whichever hole it overlaps. Run with")
        print("    --prune first if you did not mean to keep it.")


# ---------------------------------------------------------------------------


class Plan:
    def __init__(self, check: bool) -> None:
        self.check = check
        self.actions: list[str] = []
        self.warnings: list[str] = []
        # "[profile] " while do_profiles is visiting one, so a line says which.
        self.scope = ""

    def do(self, what: str, fn) -> None:
        self.actions.append(self.scope + what)
        if not self.check:
            fn()

    def warn(self, what: str) -> None:
        self.warnings.append(self.scope + what)


def browser_settings(name: str, pw: str) -> dict:
    if name == "Overlay":
        # file:// on purpose: the overlay must keep working when the mascot
        # bridge is not running. See README, "Why the overlay is file:// and
        # the mascot is http://".
        url = (REPO / "overlay.html").as_uri()
        if pw:
            url += "?pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": CANVAS_W,
            "height": CANVAS_H,
            "shutdown": False,          # keep state across scene switches
            "restart_when_active": False,
            "reroute_audio": True,      # alert audio rides the browser source
        }
    if name == "Deer":
        url = "http://127.0.0.1:%d/mascot.html?set=deer" % MASCOT_PORT
        if pw:
            url += "&pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": CANVAS_W,
            "height": CANVAS_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "OverlayV":
        # Same file:// reasoning as Overlay.
        #
        # reroute_audio stays FALSE. Alert audio rides the horizontal Overlay
        # (CLAUDE.md §4); a second rerouted browser source would put every
        # alert sound into the mix twice.
        url = (REPO / "vertical.html").as_uri()
        if pw:
            url += "?pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": VERT_W,
            "height": VERT_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "DeerV":
        # The vertical twin of Deer. Same bridge, same sprite set, different
        # placement file -- mascot.html needed no changes, because it already
        # takes `place` and sizes itself from innerWidth/innerHeight.
        url = ("http://127.0.0.1:%d/mascot.html?set=deer"
               "&place=placement-vertical.json" % MASCOT_PORT)
        if pw:
            url += "&pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": VERT_W,
            "height": VERT_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "Tts":
        # file://, like Overlay, and for a sharper reason: a browser source
        # never retries a page that failed to load, so served by a bridge that
        # was not up yet it stayed blank until refreshed -- measured, the first
        # time this source was created. From disk it always boots, and only
        # its event stream needs the bridge, which EventSource retries alone.
        # reroute_audio is the point of the whole source.
        return {
            "url": (REPO / "chat" / "tts.html").as_uri(),
            "width": 64,
            "height": 64,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": True,
        }
    if name == "Chat":
        # 800x938 is the chat hole's own aspect (2174 x 2550 page px). The
        # source is cropped to that aspect before it is stretched, so any
        # other shape throws away chat rather than letterboxing it.
        # The hole is punched, so the widget's page is what shows -- a
        # transparent chat box would read as a black rectangle cut out of the
        # panel. --peri is the chat panel's own background.
        return {"url": "about:blank", "width": 800, "height": 938,
                "css": CHAT_CSS,
                "shutdown": False, "restart_when_active": False}
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="obs-setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Standard library only")[0].strip(),
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4455)
    ap.add_argument("--password", default=os.environ.get("OBS_WS_PASSWORD", ""),
                    help="defaults to $OBS_WS_PASSWORD, then OBS's own config file")
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit non-zero if anything would")
    ap.add_argument("--placeholders", action="store_true",
                    help="create missing video sources as colour blocks, for a "
                         "machine with no capture hardware yet")
    ap.add_argument("--prune", action="store_true",
                    help="remove items from COMIC that this overlay does not manage")
    ap.add_argument("--encoder", default="", metavar="WHICH",
                    choices=["", "auto"] + sorted(ENCODER_CHOICES),
                    help="set the stream and recording video encoder: auto "
                         "(best hardware encoder this OBS reports), or one of "
                         "%s. Without it, a deprecated encoder ID is still "
                         "rewritten and a software encoder is reported."
                         % "/".join(sorted(ENCODER_CHOICES)))
    ap.add_argument("--clip", action="store_true",
                    help="log the moment to clip-marks-<date the stream "
                         "started>.csv in the clip folder -- "
                         "where it sits in the VOD, plus OBS's raw timecodes -- "
                         "and exit. This is what the deck's clip button runs")
    ap.add_argument("--go-live", dest="go_live", action="store_true",
                    help="start the main stream and the vertical one together, "
                         "and exit. Start-only: a side already live is left "
                         "alone. This is what the deck's GO LIVE button runs")
    ap.add_argument("--grade", action="store_true",
                    help="also assert the GRADE colour LUT on Cam, above CAM OFF "
                         "(generating assets/luts/kolder.cube if missing). Off "
                         "by default; without it a GRADE filter is left alone")
    ap.add_argument("--denoise", action="store_true",
                    help="also assert a mic denoiser pinned first: NV DENOISE "
                         "where OBS can run NVIDIA, else DENOISE (RNNoise). Off "
                         "by default; without it a denoiser is left alone")
    ap.add_argument("--vertical", action="store_true",
                    help="also assert %s on the vertical canvas, for streaming "
                         "9:16 alongside. Needs the Aitum Vertical Canvas "
                         "plugin and a canvas added in its dock." % VERT_SCENE)
    ap.add_argument("--export", action="store_true",
                    help="write a sanitised copy of the scene collection to "
                         "obs/comic-scenes.json and exit. Strips credentials and "
                         "machine paths, so the result is safe to commit")
    ap.add_argument("--out", default="",
                    help="--export: where to write (default obs/comic-scenes.json)")
    ap.add_argument("--export-from", dest="export_from", default="",
                    help="--export: sanitise this file instead of OBS's live one, "
                         "e.g. something you made with Scene Collection -> Export")
    ap.add_argument("--collection", default="",
                    help="--export: which collection, if you have more than one")
    ap.add_argument("--name", default="Comic Overlay",
                    help="--export: the name OBS will show for the imported "
                         "collection (default: Comic Overlay)")
    a = ap.parse_args()

    # Export reads a file. It deliberately does not need OBS running, or the
    # websocket, or a password -- you may well be exporting after quitting OBS
    # to force it to write the collection out.
    if a.export:
        return do_export(a)

    pw = a.password or discover_password()

    try:
        obs = OBS(a.host, a.port, pw)
    except (ConnectionRefusedError, OSError) as e:
        raise SystemExit(
            "error: could not reach obs-websocket at %s:%d (%s)\n"
            "       is OBS running, and is Tools -> WebSocket Server Settings\n"
            "       -> Enable WebSocket server ticked?" % (a.host, a.port, e)
        )

    # Clipping and going live are runtime actions, not setup: no plan, no
    # report, and an exit code the deck can see.
    if a.clip or a.go_live:
        rc = do_clip(obs) if a.clip else do_go_live(obs)
        obs.ws.close()
        raise SystemExit(rc)

    plan = Plan(a.check)
    layout = stack(a.placeholders)

    preflight(plan)

    # --- scenes ------------------------------------------------------------
    scenes = {s["sceneName"] for s in obs.req("GetSceneList")["scenes"]}

    if HOST_SCENE not in scenes:
        plan.do("create scene %s" % HOST_SCENE,
                lambda: obs.req("CreateScene", {"sceneName": HOST_SCENE}))
        scenes.add(HOST_SCENE)

    for name in TRIGGERS:
        if name not in scenes:
            plan.do("create scene %s" % name,
                    lambda n=name: obs.req("CreateScene", {"sceneName": n}))

    # --- inputs ------------------------------------------------------------
    inputs = {i["inputName"]: i["inputKind"] for i in obs.req("GetInputList")["inputs"]}
    kinds = set(obs.req("GetInputKindList")["inputKinds"])

    for name, kind, colour in layout:
        if name in inputs:
            if inputs[name] != kind:
                plan.warn(
                    "%s exists as %s, not %s -- left alone. Delete it in OBS and "
                    "re-run if you want this script to make it."
                    % (name, inputs[name], kind)
                )
            continue
        if kind not in kinds:
            plan.warn("%s: this OBS has no %s input kind -- creating a colour "
                      "placeholder instead" % (name, kind))
            kind, colour = "color_source_v3", colour or 0xFF404040

        settings = browser_settings(name, pw)
        if name == BROWSER_SOURCE and kind == "window_capture":
            settings = dict(BROWSER_SETTINGS)
        if kind == "color_source_v3":
            settings = {"color": colour or 0xFF404040,
                        "width": CANVAS_W, "height": CANVAS_H}
        if name == BROWSER_SOURCE:
            plan.do(
                "create input %s (%s), muted and parked -- off air until "
                "you unmute it" % (name, kind),
                lambda k=kind, s=settings: create_browser(obs, k, s),
            )
            continue
        plan.do(
            "create input %s (%s)" % (name, kind),
            lambda n=name, k=kind, s=settings: obs.req(
                "CreateInput",
                {"sceneName": HOST_SCENE, "inputName": n,
                 "inputKind": k, "inputSettings": s, "sceneItemEnabled": True},
            ),
        )

    # Browser settings are asserted every run: a wrong url, or "Shutdown source
    # when not visible" left ticked, breaks the overlay in ways that look like
    # an overlay bug.
    for name in ("Overlay", "Deer", "Chat", TTS_SOURCE):
        want = browser_settings(name, pw)
        if not want or inputs.get(name) != "browser_source":
            continue
        if name == "Chat":
            # Everything but the url, which is yours -- your channel, your
            # widget provider. The rest is derived from the hole.
            want = {k: want[k] for k in
                    ("width", "height", "css", "shutdown", "restart_when_active")}
        have = obs.req("GetInputSettings", {"inputName": name})["inputSettings"]
        diff = {k: v for k, v in want.items() if have.get(k) != v}
        # OBS omits defaults from the settings blob, so absent == the default.
        diff = {k: v for k, v in diff.items() if not (k not in have and v is False)}
        if diff:
            plan.do(
                "%s: set %s" % (name, ", ".join(sorted(diff))),
                lambda n=name, d=diff: obs.req(
                    "SetInputSettings", {"inputName": n, "inputSettings": d}),
            )

    if a.check and any(x.startswith("create input") for x in plan.actions):
        # Nothing below can be checked meaningfully against sources that do not
        # exist yet, so stop here rather than print a wall of noise.
        report(plan, a)
        return

    # --- COMIC contents and z-order ---------------------------------------
    items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
    by_name = {i["sourceName"]: i for i in items}

    for name in [n for n, _, _ in layout]:
        if name not in by_name:
            plan.do(
                "add %s to %s" % (name, HOST_SCENE),
                lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneName": HOST_SCENE, "sourceName": n, "sceneItemEnabled": True},
                ),
            )

    strays = sorted(set(by_name) - MANAGED)
    for name in strays:
        if a.prune:
            plan.do(
                "remove %s from %s" % (name, HOST_SCENE),
                lambda i=by_name[name]["sceneItemId"]: obs.req(
                    "RemoveSceneItem",
                    {"sceneName": HOST_SCENE, "sceneItemId": i}),
            )
        else:
            plan.warn(
                "%s sits in %s but no hole maps to it. It renders behind the "
                "overlay and shows through whatever hole it happens to overlap. "
                "Re-run with --prune to remove it." % (name, HOST_SCENE)
            )

    # Index 0 is the bottom of the list. Set every item explicitly rather than
    # computing a minimal set of moves: it is six requests, once.
    if not a.check or all(n in by_name for n, _, _ in layout):
        items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
        by_name = {i["sourceName"]: i for i in items}
        want_order = [n for n, _, _ in layout if n in by_name]
        have_order = [i["sourceName"] for i in
                      sorted(items, key=lambda i: i["sceneItemIndex"])
                      if i["sourceName"] in want_order]
        if have_order != want_order:
            plan.do(
                "restack %s: %s" % (HOST_SCENE, " < ".join(want_order)),
                lambda: [
                    obs.req("SetSceneItemIndex",
                            {"sceneName": HOST_SCENE,
                             "sceneItemId": by_name[n]["sceneItemId"],
                             "sceneItemIndex": i})
                    for i, n in enumerate(want_order)
                ],
            )

    # --- trigger scenes ----------------------------------------------------
    # Each holds exactly one item: COMIC, filling the canvas. The nesting is
    # the whole trick -- the browser source is never torn down, so animation
    # and websocket state survive every switch.
    want_tf = {
        "positionX": 0.0, "positionY": 0.0, "rotation": 0.0, "alignment": 5,
        "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsAlignment": 0,
        "boundsWidth": float(CANVAS_W), "boundsHeight": float(CANVAS_H),
        "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
    }
    for name in TRIGGERS:
        try:
            tit = obs.req("GetSceneItemList", {"sceneName": name})["sceneItems"]
        except ObsError:
            continue                       # only just scheduled for creation
        host = next((i for i in tit if i["sourceName"] == HOST_SCENE), None)
        if host is None:
            plan.do(
                "add %s to %s" % (HOST_SCENE, name),
                lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneName": n, "sourceName": HOST_SCENE,
                     "sceneItemEnabled": True}),
            )
            continue
        tf = host["sceneItemTransform"]
        if any(abs(float(tf.get(k, 0)) - float(vv)) > 0.5
               if isinstance(vv, float) else tf.get(k) != vv
               for k, vv in want_tf.items()):
            plan.do(
                "%s: square %s up to the canvas" % (name, HOST_SCENE),
                lambda n=name, i=host["sceneItemId"]: obs.req(
                    "SetSceneItemTransform",
                    {"sceneName": n, "sceneItemId": i,
                     "sceneItemTransform": want_tf}),
            )
        for extra in [i for i in tit if i["sourceName"] != HOST_SCENE]:
            plan.warn("%s holds %s as well as %s -- a trigger scene should hold "
                      "nothing but the nested host scene"
                      % (name, extra["sourceName"], HOST_SCENE))

    # --- chat TTS ----------------------------------------------------------
    # After the restack, which is what puts Tts into COMIC.
    do_tts(obs, plan)

    # --- audio -------------------------------------------------------------
    # After COMIC, which is what creates the Game and Browser inputs.
    do_audio(obs, plan)

    # --- mic chain ---------------------------------------------------------
    # Independent of COMIC: the mic is a global audio device off the profile,
    # not a source this script creates. Found once, shared with the ducks.
    mic = find_mic(obs, plan)
    do_mic_device(obs, plan, mic)
    if a.denoise:
        do_mic_denoise(obs, plan, mic)
    do_mic_dynamics(obs, plan, mic)

    # --- ducking -----------------------------------------------------------
    # After do_audio, which is what creates Discord.
    do_duck(obs, plan, mic)

    # --- cam kill switch ---------------------------------------------------
    # After COMIC, which is what creates the Cam input.
    do_cam_off_filter(obs, plan)

    # --- camera grade ------------------------------------------------------
    # Opt-in. After the kill switch, because it asserts its own position
    # relative to it.
    if a.grade:
        do_grade_filter(obs, plan)

    # --- clipping ----------------------------------------------------------
    # The vertical plugin's half. The profile's half runs per profile, below.
    vertical_clip_check(plan)

    # --- vertical canvas ---------------------------------------------------
    # After COMIC, because it reuses the very inputs that phase creates.
    if a.vertical:
        do_vertical(obs, plan, a, pw)

    # --- transition --------------------------------------------------------
    # The pan IS the transition. Anything else double-animates the switch.
    tr = obs.req("GetCurrentSceneTransition")
    if tr["transitionKind"] != "cut_transition":
        plan.do(
            "set transition to Cut (was %s)" % tr["transitionName"],
            lambda: obs.req("SetCurrentSceneTransition", {"transitionName": "Cut"}),
        )

    # --- profiles ----------------------------------------------------------
    # Canvas, delay, replay buffer and encoder, in every profile. Last, because
    # visiting a profile resets video and rebuilds every output.
    do_profiles(obs, plan, a)

    report(plan, a)
    obs.ws.close()


def do_profiles(obs, plan: Plan, a) -> None:
    """Assert the profile-level settings in every profile, then compare them.

    A profile here is a Restream setup. Its stream key belongs to one of the
    account's RTMP setups, each with its own channels, titles and categories,
    so switching profile is how a stream goes out as one game or another.
    Everything else a profile holds -- canvas, delay, encoder -- must be the
    same in all of them, and only the active profile can be read or written
    over the websocket. So each one is visited in turn, and the one you were
    on is put back.

    Never while anything is running: a switch resets video and rebuilds every
    output. Otherwise harmless, measured 2026-10-27 -- Overlay, OverlayV, Deer
    and DeerV stayed active through a switch and back, the vertical canvas kept
    its size, and the main key came back unchanged.
    """
    pl = obs.req("GetProfileList")
    home = pl["currentProfileName"]
    others = [n for n in pl["profiles"] if n != home]

    plan.scope = "[%s] " % home if others else ""
    do_profile(obs, plan, a)

    live = outputs_live(obs) if others else []
    if live:
        plan.scope = ""
        plan.warn("%s is running, so %s not visited -- switching profile "
                  "rebuilds every output. Re-run once it stops."
                  % (" and ".join(live), ", ".join(others)))
    elif others:
        try:
            for name in others:
                obs.switch_profile(name)
                plan.scope = "[%s] " % name
                do_profile(obs, plan, a)
        finally:
            plan.scope = ""
            obs.switch_profile(home)
    plan.scope = ""

    # From disk, which OBS writes when a profile is switched away from or its
    # settings are OK'd -- so this holds even while live, when nothing above
    # could visit the others.
    profs = read_profiles()
    if len(profs) < 2:
        return

    same = {}
    for name, p in profs.items():
        if p["key"]:
            same.setdefault(p["key"], []).append(name)
    for names in same.values():
        if len(names) > 1:
            plan.warn(
                "profiles %s stream on the same key, so they go to the same "
                "Restream setup and switching between them changes nothing. "
                "Give each its own setup's key: Restream home -> that setup's "
                "card -> stream key, then Settings -> Stream -> Use Stream Key"
                % " and ".join(sorted(names)))

    # Connect Account fetches the account's key at login and OBS writes it over
    # whatever key the profile holds (RestreamAuth / OAuthStreamKey in OBS's
    # source), so a connected profile is always the default setup.
    linked = sorted(n for n, p in profs.items() if p["auth"] == "Restream")
    if len(linked) > 1:
        plan.warn(
            "profiles %s are each connected to the Restream account. A connected "
            "profile always streams on the account's default key -- OBS writes "
            "it over one you paste -- so all of them go to Default RTMP. Keep "
            "the account in one; in the rest, Settings -> Stream -> Disconnect "
            "Account, then Use Stream Key" % ", ".join(linked))

    # Not asserted -- bitrate is yours -- but it should be the same yours in
    # every profile, and a profile made with Profile -> New is not.
    base = (profs.get(home) or {}).get("encoder") or {}
    for name, p in sorted(profs.items()):
        if name == home:
            continue
        diff = sorted(k for k in set(base) | set(p["encoder"])
                      if base.get(k) != p["encoder"].get(k))
        if diff:
            plan.warn(
                "profile %s encodes differently from %s (%s). Profiles here "
                "should differ by stream key only: Profile -> Duplicate copies "
                "these, Profile -> New starts on OBS's defaults, and no "
                "websocket request reaches them -- Settings -> Output"
                % (name, home, ", ".join(
                    "%s %s -> %s" % (k, base.get(k, "default"),
                                     p["encoder"].get(k, "default"))
                    for k in diff)))


def do_profile(obs, plan: Plan, a) -> None:
    """Everything this overlay needs from the active profile."""
    v = obs.req("GetVideoSettings")
    if (v["baseWidth"], v["baseHeight"]) != (CANVAS_W, CANVAS_H):
        plan.warn(
            "canvas is %dx%d, this overlay assumes %dx%d -- every hole rect it "
            "pushes is in canvas pixels, so fix this in Settings -> Video first"
            % (v["baseWidth"], v["baseHeight"], CANVAS_W, CANVAS_H)
        )
    # A profile made with Profile -> New starts at 1280x720 and 30 fps under a
    # 1920x1080 canvas (measured 2026-10-27), which the canvas check passes.
    if (v["outputWidth"], v["outputHeight"]) != (v["baseWidth"], v["baseHeight"]):
        plan.warn(
            "output is scaled to %dx%d from the %dx%d canvas, so the stream goes "
            "out softer than the overlay is drawn. Settings -> Video -> Output "
            "(Scaled) Resolution"
            % (v["outputWidth"], v["outputHeight"], v["baseWidth"], v["baseHeight"])
        )
    fps = v["fpsNumerator"] / max(1, v["fpsDenominator"])
    if fps < 60:
        plan.warn("video runs at %g fps; this overlay is built at 60. "
                  "Settings -> Video -> Common FPS Values" % fps)

    s = obs.req("GetStreamServiceSettings").get("streamServiceSettings") or {}
    if not s.get("key"):
        plan.warn("no stream key. Settings -> Stream")
    if "restream.io" not in (s.get("server") or ""):
        plan.warn(
            "streams to %s, not Restream. The vertical stream rides Restream's "
            "/vertical ingest on this profile's key, so it has nowhere to go"
            % (s.get("server") or s.get("service") or "nothing"))

    do_clipping(obs, plan)
    do_encoder(obs, plan, a)


def outputs_live(obs) -> list:
    """Whatever is running that a profile switch would tear down."""
    live = []
    for kind, what in (("GetStreamStatus", "the stream"),
                       ("GetRecordStatus", "a recording"),
                       ("GetVirtualCamStatus", "the virtual camera"),
                       ("GetReplayBufferStatus", "the replay buffer")):
        try:
            if obs.req(kind).get("outputActive"):
                live.append(what)
        except ObsError:
            pass                           # no such output in this OBS
    try:
        r = obs.req("CallVendorRequest",
                    {"vendorName": VERT_VENDOR, "requestType": "status",
                     "requestData": {"width": VERT_W, "height": VERT_H}})
        d = r.get("responseData") or {}
        if d.get("success") and d.get("streaming"):
            live.append("the vertical stream")
    except ObsError:
        pass
    return live


def read_profiles() -> dict:
    """Profile name -> what is on disk for it. Read-only.

    The folder is not the name -- OBS strips a name to make the folder, so
    'zz-probe' became zzprobe -- so each is matched by the Name in its own
    basic.ini. Keys are hashed on the way in, and never kept or printed.
    """
    out = {}
    try:
        dirs = [d for d in (obs_config_dir() / "basic" / "profiles").iterdir()
                if (d / "basic.ini").is_file()]
    except OSError:
        return out
    for d in dirs:
        ini = configparser.ConfigParser(interpolation=None, strict=False)
        ini.optionxform = str
        try:
            ini.read_string((d / "basic.ini").read_text(encoding="utf-8-sig",
                                                        errors="replace"))
        except (OSError, configparser.Error):
            continue
        blobs = {}
        for f in ("service.json", "streamEncoder.json"):
            try:
                blobs[f] = json.loads((d / f).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                blobs[f] = {}
        key = (blobs["service.json"].get("settings") or {}).get("key") or ""
        out[ini.get("General", "Name", fallback=d.name)] = {
            "auth": ini.get("Auth", "Type", fallback=""),
            "key": hashlib.sha256(key.encode()).hexdigest() if key else "",
            "encoder": blobs["streamEncoder.json"],
        }
    return out


def do_clipping(obs, plan: Plan) -> None:
    """Replay buffer off in both output modes, stream delay on -- this profile."""
    def param(cat, key):
        return obs.req("GetProfileParameter",
                       {"parameterCategory": cat,
                        "parameterName": key})["parameterValue"]

    def want(cat, key, value, why):
        if (param(cat, key) or "") != value:
            plan.do("%s: %s -> %s  (%s)" % (cat, key, value, why),
                    lambda c=cat, k=key, v=value: obs.req(
                        "SetProfileParameter",
                        {"parameterCategory": c, "parameterName": k,
                         "parameterValue": v}))

    for cat in ("SimpleOutput", "AdvOut"):
        want(cat, "RecRB", "false", "clips are timestamps, not a buffer")

    # OBS builds the buffer output from RecRB at launch and never again, so
    # the request answering at all means this OBS still has one: the button
    # stays, and "start replay buffer when streaming" would still start it.
    # Stopping is a one-way door -- it will not start again before a restart
    # -- which is what is wanted now.
    try:
        buf = obs.req("GetReplayBufferStatus")
    except ObsError:
        buf = None
    if buf is not None:
        if buf.get("outputActive"):
            plan.do("stop the replay buffer (holds RAM, nothing saves it now)",
                    lambda: obs.req("StopReplayBuffer"))
        plan.warn("restart OBS once -- it still has the replay buffer it "
                  "built at launch, and only a restart drops it")

    want("Output", "DelayEnable", "true", "stream delay")
    want("Output", "DelaySec", str(STREAM_DELAY), "%ds" % STREAM_DELAY)
    # A reconnect resumes where it cut off rather than skipping ahead, so the
    # VOD has no hole -- at the cost of the delay growing by the outage.
    want("Output", "DelayPreserve", "true", "no hole in the VOD on reconnect")


def vertical_clip_check(plan: Plan) -> None:
    """The vertical plugin's side of clipping and the delay. Reported only.

    OBS rewrites the plugin's config on exit, and it is one file whichever
    profile is active, so this runs once rather than per profile.
    """
    canvas = vertical_plugin_settings()
    # Not just RAM: with backtrack on, the plugin sets RecRB true in both
    # output modes every time OBS loads it, undoing the assert above.
    if canvas.get("backtrack"):
        plan.warn("vertical backtrack is on -- %ss in RAM for a clip nothing "
                  "saves, and it turns RecRB back on at every OBS launch. "
                  "Untick 'Backtrack runs while streaming/recording' in the "
                  "vertical dock's settings" % canvas.get("backtrack_seconds"))
    # Read from Aitum's source (vertical-canvas.cpp, where it creates the stream
    # output); Restream's build carries the same keys. Without advanced stream
    # settings the main delay applies, so only that mode can disagree.
    if canvas.get("stream_advanced_settings"):
        vdelay = (int(canvas.get("stream_delay_duration") or 0)
                  if canvas.get("stream_delay_enabled") else 0)
        if vdelay != STREAM_DELAY:
            plan.warn("vertical stream delay is %ss, main is %ss -- its advanced "
                      "stream settings override the main delay, so the vertical "
                      "stream goes out that much ahead" % (vdelay, STREAM_DELAY))


def vertical_plugin_settings() -> dict:
    """The vertical plugin's saved settings for its canvas, or {} if none.

    This is the file on disk, which the plugin writes when its settings dialog
    is OK'd and OBS rewrites on exit -- read-only here, always.
    """
    cfg = obs_config_dir() / "plugin_config" / "vertical-canvas" / "config.json"
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))["canvas"][0]
    except (OSError, ValueError, KeyError, IndexError):
        return {}


def do_clip(obs) -> int:
    """Append the press to clip_marks(). Returns an exit code the deck can see.

    `vod` is where what you saw at the press sits in the VOD or Restream's
    recording: OBS's stream time plus the delay. libobs counts a frame when it
    *sends* it, after the delay queue has held it back, so its stream time is
    what viewers are seeing and the moment you pressed on is `delay` further
    on -- read from libobs's source, not yet measured on a delayed stream.
    Give or take the few seconds Restream and the platform trim off the start;
    a reconnect with the delay preserved adds its outage on top.

    During the countdown after Start Streaming nothing has been sent, so a
    press there gets the time and no position. `recording` is a local
    recording's timecode, which is never delayed, so it is exact.
    """
    def seconds(kind):
        try:
            st = obs.req(kind)
        except ObsError:
            return 0
        return st.get("outputDuration", 0) // 1000 if st.get("outputActive") else 0

    def param(key):
        return obs.req("GetProfileParameter",
                       {"parameterCategory": "Output",
                        "parameterName": key})["parameterValue"] or ""

    def hms(s):
        return "%02d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s else ""

    now = datetime.now().astimezone()
    sent, rec = seconds("GetStreamStatus"), seconds("GetRecordStatus")
    delay = int(param("DelaySec") or 0) if param("DelayEnable") == "true" else 0
    # When whatever is running was started: Start Streaming was clicked `delay`
    # before the first frame went out. Nothing running, or still counting
    # down, and it is now.
    marks = clip_marks(now - timedelta(seconds=max(sent and sent + delay, rec)))
    row = [now.isoformat(sep=" ", timespec="seconds"),
           hms(sent and sent + delay), hms(sent), str(delay), hms(rec)]
    try:
        marks.parent.mkdir(parents=True, exist_ok=True)
        new = not marks.exists() or marks.stat().st_size == 0
        with marks.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "vod", "stream", "delay", "recording"])
            w.writerow(row)
    except OSError as e:
        # Excel holds an open CSV locked. Print the row so the moment is not lost.
        print("could not write %s (%s) -- the mark was: %s"
              % (marks, e, ",".join(row)), file=sys.stderr)
        return 1
    print("marked: %s  vod %s" % (row[0], row[1] or "-- not sending yet"))
    return 0


def do_go_live(obs) -> int:
    """Start the main stream and the vertical one together. Returns an exit code.

    Start-only, never a toggle: a press while live must not end the stream, so
    a side that is already up is left alone.

    Main goes first -- Restream's plugin repoints the main stream at its
    `/horizontal` ingest on OBS's "streaming starting", and its own Autostart
    always starts the vertical after that. The vertical start is asked of the
    plugin's vendor, which queues it onto the dock and answers before it has
    happened, so both sides are confirmed by polling, not taken from replies.

    With a delay, a stream output reports active from the click, through its
    countdown. So when the main countdown ends and the plugin's Autostart
    fires, it finds the vertical already running and returns. Without a delay
    an output reports active only once connected, and a second start could land
    mid-connect -- so then the vertical is left to Autostart, if it is on.
    """
    dims = {"width": VERT_W, "height": VERT_H}

    def param(key):
        return obs.req("GetProfileParameter",
                       {"parameterCategory": "Output",
                        "parameterName": key})["parameterValue"] or ""

    def main_live():
        return bool(obs.req("GetStreamStatus").get("outputActive"))

    def vert_live():
        """True / False, or None when the plugin answers no vendor."""
        try:
            r = obs.req("CallVendorRequest", {"vendorName": VERT_VENDOR,
                                              "requestType": "status",
                                              "requestData": dims})
        except ObsError:
            return None
        d = r.get("responseData") or {}
        return bool(d.get("streaming")) if d.get("success") else None

    def wait(check, seconds):
        end = time.time() + seconds
        while not check() and time.time() < end:
            time.sleep(0.25)
        return check()

    delay = int(param("DelaySec") or 0) if param("DelayEnable") == "true" else 0
    autostart = bool(vertical_plugin_settings().get("streaming_match_main"))
    was_live = main_live()

    if was_live:
        print("main: already live")
    else:
        try:
            obs.req("StartStream")
        except ObsError as e:
            print("main: OBS refused to start -- %s" % e, file=sys.stderr)
            return 1
        # A delayed output is active at once; an undelayed one once connected.
        if not wait(main_live, 15):
            print("main: asked to start, but OBS never reported it running "
                  "-- check the stream settings", file=sys.stderr)
            return 1
        print("main: started")

    v = vert_live()
    if v is None:
        print("vertical: the plugin answers no '%s' vendor -- start it from "
              "the vertical dock" % VERT_VENDOR, file=sys.stderr)
        return 1
    if v:
        print("vertical: already live")
    elif not delay and autostart:
        v = wait(vert_live, 15)
        print("vertical: started by the plugin's Autostart" if v else
              "vertical: Autostart did not start it -- use the vertical dock")
    else:
        obs.req("CallVendorRequest", {"vendorName": VERT_VENDOR,
                                      "requestType": "start_streaming",
                                      "requestData": dims})
        v = wait(vert_live, 5)
        print("vertical: started" if v else
              "vertical: asked to start, but the plugin never reported it "
              "running -- use the vertical dock")

    if delay and not was_live:
        print("on air at about %s (%ds delay); stopping drains it the same way"
              % (datetime.fromtimestamp(time.time() + delay)
                 .strftime("%H:%M:%S"), delay))
    return 0 if v else 1


def create_browser(obs, kind: str, settings: dict) -> None:
    """Create Browser off air: muted and off-canvas before anything sees it.

    A fresh capture lands enabled at 0,0, above Game, and neither overlay
    hears about it until its next scene change -- a window of desktop on
    stream. So the item is created disabled, muted, parked, and only then
    enabled. Enabled matters too: a disabled item is an inactive capture, and
    the first unmute would wait out a re-hook in black.
    """
    made = obs.req("CreateInput", {
        "sceneName": HOST_SCENE, "inputName": BROWSER_SOURCE,
        "inputKind": kind, "inputSettings": settings,
        "sceneItemEnabled": False})
    item = {"sceneName": HOST_SCENE, "sceneItemId": made["sceneItemId"]}
    obs.req("SetInputMute", {"inputName": BROWSER_SOURCE, "inputMuted": True})
    obs.req("SetSceneItemTransform", dict(item, sceneItemTransform=PARK))
    obs.req("SetSceneItemEnabled", dict(item, sceneItemEnabled=True))


def do_audio(obs, plan: Plan) -> None:
    """One capture per application, and none of a whole output device.

    Capture Audio on Game and Browser is asserted both ways: on when nothing
    captures a whole output, off while something does, so a sound never
    reaches the stream twice in either state.
    """
    inputs = {i["inputName"]: i["inputKind"]
              for i in obs.req("GetInputList")["inputs"]}
    whole = sorted(n for n, k in inputs.items() if k in OUTPUT_CAPTURE_KINDS)
    per_app = not whole

    if whole:
        plan.warn(
            "%s captures a whole output device, which already carries the "
            "game, the browser and Discord -- so until it is gone, Capture "
            "Audio stays off on %s and %s and no %s capture is added, or every "
            "one of them would reach the stream twice and comb-filter. Disable "
            "it: Settings -> Audio -> Global Audio Devices -> Desktop Audio -> "
            "Disabled (or remove it, if it is a source you added), then run "
            "this again." % (" and ".join(whole), GAME_SOURCE, BROWSER_SOURCE,
                             DISCORD_SOURCE))

    # Only a real game or window capture has the tickbox; a placeholder colour
    # source or a macOS screen capture has nothing to assert here.
    for name, kind in ((GAME_SOURCE, "game_capture"),
                       (BROWSER_SOURCE, "window_capture")):
        if inputs.get(name) != kind:
            continue
        have = obs.req("GetInputSettings",
                       {"inputName": name})["inputSettings"]
        if bool(have.get("capture_audio")) != per_app:
            plan.do(
                "turn %s Capture Audio on %s -- %s"
                % ("on" if per_app else "off", name,
                   "it is the only path for that sound now" if per_app else
                   "%s already carries it, and two copies comb-filter"
                   % whole[0]),
                lambda n=name: obs.req("SetInputSettings", {
                    "inputName": n,
                    "inputSettings": {"capture_audio": per_app},
                }),
            )

    if DISCORD_SOURCE in inputs:
        if inputs[DISCORD_SOURCE] != DISCORD_KIND:
            plan.warn("%s exists as %s, not %s -- left alone. Delete it in OBS "
                      "and re-run if you want this script to make it."
                      % (DISCORD_SOURCE, inputs[DISCORD_SOURCE], DISCORD_KIND))
        elif whole:
            plan.warn("%s and %s both carry Discord, so friends' voices go out "
                      "twice until %s is gone"
                      % (DISCORD_SOURCE, whole[0], whole[0]))
    elif per_app:
        plan.do(
            "create input %s (%s, Discord.exe)" % (DISCORD_SOURCE, DISCORD_KIND),
            lambda: obs.req("CreateInput", {
                "sceneName": HOST_SCENE, "inputName": DISCORD_SOURCE,
                "inputKind": DISCORD_KIND,
                "inputSettings": dict(DISCORD_SETTINGS),
                "sceneItemEnabled": True}),
        )



def do_tts(obs, plan: Plan) -> None:
    """Park the Tts source off-canvas and assert how it is monitored.

    Mute is never asserted: it is a live toggle the deck owns, the way CAM
    OFF's enabled state is.
    """
    try:
        items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
    except ObsError:
        return
    item = next((i for i in items if i["sourceName"] == TTS_SOURCE), None)
    if item is None:
        return                         # only just scheduled; the next run parks it
    tf = item["sceneItemTransform"]
    if any(abs(float(tf.get(k, 0)) - v) > 0.5 for k, v in PARK.items()):
        plan.do(
            "park %s off-canvas" % TTS_SOURCE,
            lambda: obs.req("SetSceneItemTransform",
                            {"sceneName": HOST_SCENE,
                             "sceneItemId": item["sceneItemId"],
                             "sceneItemTransform": PARK}),
        )
    try:
        have = obs.req("GetInputAudioMonitorType",
                       {"inputName": TTS_SOURCE})["monitorType"]
    except ObsError:
        return
    if have != TTS_MONITOR:
        plan.do(
            "%s: audio monitoring %s (was %s)"
            % (TTS_SOURCE, TTS_MONITOR.rsplit("_TYPE_", 1)[-1].lower(),
               have.rsplit("_TYPE_", 1)[-1].lower()),
            lambda: obs.req("SetInputAudioMonitorType",
                            {"inputName": TTS_SOURCE, "monitorType": TTS_MONITOR}),
        )


def find_mic(obs, plan: Plan):
    """The microphone input, or None.

    Not hardcoded to a name. `Mic/Aux` is OBS's own label for the first global
    audio device, it is localised, and this script never creates it -- it comes
    off the profile, not out of COMIC. So the mic is found by input *kind*, and
    the name is only a tie-break for a machine with more than one capture
    device wired up. Two of them and no `Mic/Aux` is not guessable, so it says
    so rather than filtering the wrong one.
    """
    ins = [i for i in obs.req("GetInputList")["inputs"]
           if i["inputKind"] in MIC_KINDS]
    if not ins:
        plan.warn("no audio input capture in this profile, so there is no mic "
                  "to denoise or duck under -- add one under Settings -> Audio")
        return None
    if len(ins) == 1:
        return ins[0]["inputName"]
    if any(i["inputName"] == MIC_SOURCE for i in ins):
        return MIC_SOURCE
    plan.warn("%d audio input captures and none called %r, so this script "
              "cannot tell which is the mic: %s"
              % (len(ins), MIC_SOURCE,
                 ", ".join(i["inputName"] for i in ins)))
    return None


def do_mic_device(obs, plan: Plan, mic) -> None:
    """Repoint the mic at a device that exists, when its saved one does not.

    OBS saves the mic as a WASAPI endpoint id, and Windows issues a new one
    whenever it reinstalls the device -- a driver install, another USB port.
    2026-10-29: after a reboot that followed a live NVIDIA driver install, the
    USB Condenser Microphone came back as {651cc1af-...} while OBS still held
    {c9702c9a-...}. The log said "failed to start" once; the source stayed
    enabled, unmuted and active, and its meter never moved. So a saved id that
    OBS no longer offers is repointed when exactly one real device is left, and
    the candidates are named otherwise. `default` is always offered.
    """
    if mic is None:
        return
    have = obs.req("GetInputSettings",
                   {"inputName": mic})["inputSettings"].get("device_id")
    items = obs.req("GetInputPropertiesListPropertyItems",
                    {"inputName": mic, "propertyName": "device_id"})["propertyItems"]
    if have in (None, "default") or any(i["itemValue"] == have for i in items):
        return
    real = [i for i in items if i["itemValue"] != "default"]
    if len(real) == 1:
        plan.do(
            "repoint %s at %s -- the device it was saved with no longer "
            "exists, so it is capturing nothing" % (mic, real[0]["itemName"]),
            lambda: obs.req("SetInputSettings", {
                "inputName": mic,
                "inputSettings": {"device_id": real[0]["itemValue"]}}),
        )
    else:
        plan.warn("%s is saved against a device that no longer exists, so it "
                  "is capturing nothing -- pick one in its properties: %s"
                  % (mic, ", ".join(i["itemName"] for i in real) or "none found"))


def do_mic_denoise(obs, plan: Plan, mic) -> None:
    """Assert one denoiser at the top of the mic's chain: NVIDIA if it can run.

    Order is asserted for the same reason it is on the Cam chain, and for the
    opposite-facing reason: anything that lifts level -- gain, a compressor, an
    upward compressor -- lifts the noise floor with it, so suppression running
    after one has to undo work the chain just did. A gate below it also reads a
    cleaner signal and can sit closer to the voice. A compressor or a gain
    filter added by hand is exactly the case, and the pin keeps the denoiser
    above it -- COMPRESS's +20 dB once was. Both denoisers are pinned, the
    one in use first and the other directly under it, so the fallback is already
    in place the day it is switched on.

    Enabled state is reported, not asserted, bar the two hand-overs described
    above DENOISE_FILTER. Toggling a denoiser off to hear the difference is a
    legitimate live action, and this script does not overrule live toggles --
    but a mic with no denoiser on is worth one line.
    """
    if mic is None:
        return

    nvidia = NV_DENOISE_KIND in obs.req("GetSourceFilterKindList")["sourceFilterKinds"]
    filters = obs.req("GetSourceFilterList", {"sourceName": mic})["filters"]
    by_name = {f["filterName"]: f for f in filters}
    nv = by_name.get(NV_DENOISE_FILTER)
    rn = by_name.get(DENOISE_FILTER)

    for name, kind, have in ((NV_DENOISE_FILTER, NV_DENOISE_KIND, nv),
                             (DENOISE_FILTER, DENOISE_KIND, rn)):
        if have is not None and have["filterKind"] != kind:
            plan.warn(
                "%s on %s is a %s, not a %s -- rename or remove it, this script "
                "will not overwrite a filter it did not make"
                % (name, mic, have["filterKind"], kind))
            return

    created = []

    def create(name, kind, settings, what):
        created.append(name)
        plan.do(
            "add %s filter to %s (%s)" % (name, mic, what),
            lambda: obs.req("CreateSourceFilter", {
                "sourceName": mic, "filterName": name, "filterKind": kind,
                "filterSettings": dict(settings), "filterEnabled": True}),
        )

    def switch(name, on, why):
        plan.do(
            "switch %s %s on %s -- %s" % (name, "on" if on else "off", mic, why),
            lambda: obs.req("SetSourceFilterEnabled", {
                "sourceName": mic, "filterName": name, "filterEnabled": on}),
        )

    if nv is not None:
        method = (nv.get("filterSettings") or {}).get("method")
        if method is not None and method not in NV_DENOISE_METHODS:
            plan.warn("%s on %s is set to %r, which takes out room echo and no "
                      "noise -- pick a method with 'denoiser' in it"
                      % (NV_DENOISE_FILTER, mic, method))
    if rn is not None:
        # An absent key means OBS is holding the v2 default, which is RNNoise
        # wherever it was compiled in -- so absent is fine, and `speex` is a
        # choice. Only a method that is neither cannot work.
        method = (rn.get("filterSettings") or {}).get("method")
        if method is not None and method not in ("rnnoise", "speex"):
            plan.do(
                "%s on %s is set to %r, which is not a method OBS has -- reset "
                "it to RNNoise" % (DENOISE_FILTER, mic, method),
                lambda: obs.req("SetSourceFilterSettings", {
                    "sourceName": mic,
                    "filterName": DENOISE_FILTER,
                    "filterSettings": dict(DENOISE_SETTINGS),
                }),
            )

    # What is on once this run's own changes land. A --check run has not made
    # them, and its report has to describe the chain the run would leave.
    nv_on = nv is not None and nv.get("filterEnabled", True)
    rn_on = rn is not None and rn.get("filterEnabled", True)

    if nvidia:
        if nv is None:
            create(NV_DENOISE_FILTER, NV_DENOISE_KIND, NV_DENOISE_SETTINGS,
                   "NVIDIA Noise Removal")
            nv_on = True
            if rn_on:
                switch(DENOISE_FILTER, False, "%s replaces it, and two "
                       "denoisers in a row thin the voice" % NV_DENOISE_FILTER)
                rn_on = False
        elif nv_on and rn_on:
            plan.warn("%s and %s are both on on %s -- two denoisers in a row "
                      "thin the voice; switch %s off"
                      % (NV_DENOISE_FILTER, DENOISE_FILTER, mic, DENOISE_FILTER))
        order = (NV_DENOISE_FILTER, DENOISE_FILTER)
    else:
        if nv is not None:
            plan.warn("%s on %s cannot run: OBS has no NVIDIA Audio Effects on "
                      "this machine, so it passes the mic through untouched. "
                      "Install the Audio Effects SDK redistributable for this "
                      "GPU (RTX only) and restart OBS; RNNoise stands in until "
                      "then" % (NV_DENOISE_FILTER, mic))
            nv_on = False
        if rn is None:
            create(DENOISE_FILTER, DENOISE_KIND, DENOISE_SETTINGS, "RNNoise")
            rn_on = True
        elif not rn_on and nv is not None:
            switch(DENOISE_FILTER, True, "it is the fallback for %s, which "
                   "cannot run here" % NV_DENOISE_FILTER)
            rn_on = True
        order = (DENOISE_FILTER, NV_DENOISE_FILTER)

    if not (nv_on or rn_on):
        plan.warn("no denoiser is on on %s, so the mic is going out raw" % mic)

    # Position, asserted last for the same reason the grade's is: a freshly
    # created filter lands at the *bottom* of the chain, which is the one place
    # a denoiser must not be. A --check run has created nothing, so its filters
    # are put where creation would put them, and the list is moved along with
    # each request: either way the report names the moves a real run makes.
    cur = [f["filterName"]
           for f in obs.req("GetSourceFilterList", {"sourceName": mic})["filters"]]
    cur += [n for n in created if n not in cur]
    present = [n for n in order if n in cur]
    for want, name in enumerate(present):
        if cur.index(name) == want:
            continue
        where = ("to the top of %s's chain" % mic if want == 0
                 else "directly under %s" % present[0])
        plan.do(
            "move %s %s -- under anything that lifts level it is "
            "denoising a floor that was just raised" % (name, where),
            lambda n=name, w=want: obs.req("SetSourceFilterIndex", {
                "sourceName": mic, "filterName": n, "filterIndex": w}),
        )
        cur.remove(name)
        cur.insert(want, name)


def do_mic_dynamics(obs, plan: Plan, mic) -> None:
    """Assert EQ, COMPRESS and LIMIT at the bottom of the chain, in that order.

    Settings are written only at creation; they are tuned by ear. Enabled
    state is reported, not asserted, the way the denoisers' is.
    """
    if mic is None:
        return
    filters = obs.req("GetSourceFilterList", {"sourceName": mic})["filters"]
    by_name = {f["filterName"]: f for f in filters}
    created = []

    for name, kind, settings in MIC_DYNAMICS:
        have = by_name.get(name)
        if have is None:
            # A new filter lands at the bottom; MIC_DYNAMICS is created in
            # list order, so a fresh chain needs no moves.
            created.append(name)
            plan.do(
                "add %s filter to %s (%s)" % (name, mic, kind),
                lambda n=name, k=kind, s=settings: obs.req("CreateSourceFilter", {
                    "sourceName": mic, "filterName": n, "filterKind": k,
                    "filterSettings": dict(s), "filterEnabled": True}),
            )
        elif have["filterKind"] != kind:
            plan.warn(
                "%s on %s is a %s, not a %s -- rename or remove it, this script "
                "will not overwrite a filter it did not make"
                % (name, mic, have["filterKind"], kind))
        elif not have.get("filterEnabled", True):
            plan.warn("%s on %s is switched off" % (name, mic))

    # Position, asserted after creation for the denoisers' reason: a filter
    # added by hand lands at the bottom, under the limiter, where it can push
    # the voice past the ceiling the limiter just set. Placed from the last one
    # up, so each move leaves the ones already placed below it where they are.
    # A --check run has created nothing, so its filters are put where creation
    # would put them, as do_mic_denoise does.
    cur = [f["filterName"]
           for f in obs.req("GetSourceFilterList", {"sourceName": mic})["filters"]]
    cur += [n for n in created if n not in cur]
    names = [n for n, _, _ in MIC_DYNAMICS if n in cur]
    for i in reversed(range(len(names))):
        name, want = names[i], len(cur) - len(names) + i
        if cur.index(name) == want:
            continue
        plan.do(
            "move %s to position %d of %d in %s's chain -- %s"
            % (name, want + 1, len(cur), mic,
               "anything under a limiter can push past its ceiling"
               if name == names[-1] else "EQ, then COMPRESS, then LIMIT"),
            lambda n=name, w=want: obs.req("SetSourceFilterIndex", {
                "sourceName": mic, "filterName": n, "filterIndex": w}),
        )
        cur.remove(name)
        cur.insert(want, name)


def do_duck(obs, plan: Plan, mic) -> None:
    """Assert each DUCKS sidechain compressor on its target, keyed as listed.

    Only the sidechain is asserted after creation. Threshold, attack and release
    are taste, tuned by ear, and a setup run must not undo that. Enabled state
    is reported, not asserted, the way the denoisers' is.
    """
    inputs = {i["inputName"] for i in obs.req("GetInputList")["inputs"]}
    for target, name, key, settings in DUCKS:
        key = mic if key is MIC_KEY else key
        if key is None or target not in inputs or key not in inputs:
            continue  # find_mic / do_audio / COMIC have already said why
        filters = obs.req("GetSourceFilterList",
                          {"sourceName": target})["filters"]
        have = next((f for f in filters if f["filterName"] == name), None)
        if have is not None and have["filterKind"] != DUCK_KIND:
            plan.warn(
                "%s on %s is a %s, not a %s -- rename or remove it, this script "
                "will not overwrite a filter it did not make"
                % (name, target, have["filterKind"], DUCK_KIND))
            continue

        if have is None:
            plan.do(
                "add %s filter to %s (ducks under %s)" % (name, target, key),
                lambda t=target, n=name, k=key, s=settings: obs.req(
                    "CreateSourceFilter", {
                        "sourceName": t,
                        "filterName": n,
                        "filterKind": DUCK_KIND,
                        "filterSettings": dict(s, sidechain_source=k),
                        "filterEnabled": True,
                    }),
            )
            continue

        side = (have.get("filterSettings") or {}).get("sidechain_source", "none")
        if side != key:
            plan.do(
                "point %s on %s at %s (was %r) -- without it the filter only "
                "compresses %s" % (name, target, key, side, target),
                lambda t=target, n=name, k=key: obs.req(
                    "SetSourceFilterSettings", {
                        "sourceName": t,
                        "filterName": n,
                        "filterSettings": {"sidechain_source": k},
                    }),
            )
        if not have.get("filterEnabled", True):
            plan.warn("%s on %s is switched off, so %s will not duck under %s"
                      % (name, target, target, key))


def do_cam_off_filter(obs, plan: Plan) -> None:
    """Assert the CAM OFF filter on the Cam input.

    Idempotent, and deliberately does not touch the filter's enabled state: it
    is a live toggle the deck drives, so a setup run must not decide for it.
    """
    try:
        filters = obs.req(
            "GetSourceFilterList", {"sourceName": CAM_OFF_SOURCE})["filters"]
    except ObsError:
        return                       # Cam only just scheduled for creation

    have = next(
        (f for f in filters if f["filterName"] == CAM_OFF_FILTER), None)

    if have is None:
        plan.do(
            "add %s filter to %s" % (CAM_OFF_FILTER, CAM_OFF_SOURCE),
            lambda: obs.req("CreateSourceFilter", {
                "sourceName": CAM_OFF_SOURCE,
                "filterName": CAM_OFF_FILTER,
                "filterKind": CAM_OFF_KIND,
                "filterSettings": CAM_OFF_SETTINGS,
                "filterEnabled": False,
            }),
        )
        return

    if have["filterKind"] != CAM_OFF_KIND:
        plan.warn(
            "%s on %s is a %s, not a %s -- rename or remove it, this script "
            "will not overwrite a filter it did not make"
            % (CAM_OFF_FILTER, CAM_OFF_SOURCE, have["filterKind"], CAM_OFF_KIND))
        return

    settings = have.get("filterSettings") or {}
    # An absent key means OBS is holding the default, which is white.
    if settings.get("color_multiply", 16777215) != 0:
        plan.do(
            "%s on %s does not multiply to black -- reset it"
            % (CAM_OFF_FILTER, CAM_OFF_SOURCE),
            lambda: obs.req("SetSourceFilterSettings", {
                "sourceName": CAM_OFF_SOURCE,
                "filterName": CAM_OFF_FILTER,
                "filterSettings": CAM_OFF_SETTINGS,
            }),
        )


def do_grade_filter(obs, plan: Plan) -> None:
    """Assert the camera grade LUT on the Cam input, above the kill switch.

    The .cube is generated rather than committed: it is ~860 KB of derived
    text, assets/* is gitignored, and tools/cam-grade.py is deterministic, so a
    fresh clone regenerates it instead of carrying it around. That keeps the
    "install OBS, run this" promise without a large blob in the history.
    """
    try:
        filters = obs.req(
            "GetSourceFilterList", {"sourceName": CAM_OFF_SOURCE})["filters"]
    except ObsError:
        return                       # Cam only just scheduled for creation

    have = next((f for f in filters if f["filterName"] == GRADE_FILTER), None)

    if have is not None and have["filterKind"] != GRADE_KIND:
        plan.warn(
            "%s on %s is a %s, not a %s -- rename or remove it, this script "
            "will not overwrite a filter it did not make"
            % (GRADE_FILTER, CAM_OFF_SOURCE, have["filterKind"], GRADE_KIND))
        return

    # The table itself, if this machine has never generated it.
    if not GRADE_LUT.exists():
        if not GRADE_GENERATOR.exists():
            plan.warn(
                "%s is missing and tools/cam-grade.py is not there to generate "
                "it, so the camera grade cannot be asserted"
                % GRADE_LUT.relative_to(REPO).as_posix())
            return
        plan.do(
            "generate %s" % GRADE_LUT.relative_to(REPO).as_posix(),
            lambda: subprocess.run(
                [sys.executable, str(GRADE_GENERATOR), "-o", str(GRADE_LUT)],
                check=True, capture_output=True),
        )

    if have is None:
        plan.do(
            "add %s filter to %s (%s)"
            % (GRADE_FILTER, CAM_OFF_SOURCE, GRADE_LUT.name),
            lambda: obs.req("CreateSourceFilter", {
                "sourceName": CAM_OFF_SOURCE,
                "filterName": GRADE_FILTER,
                "filterKind": GRADE_KIND,
                "filterSettings": {"image_path": str(GRADE_LUT),
                                   "clut_amount": 1.0},
                "filterEnabled": True,
            }),
        )
    else:
        # Repair only a path that cannot work: absent, or somewhere this script
        # did not put it. A different LUT in assets/luts is a choice, not a
        # fault, so it is left alone.
        path = (have.get("filterSettings") or {}).get("image_path") or ""
        ok = False
        if path:
            try:
                candidate = Path(path)
                ok = (candidate.exists()
                      and candidate.resolve().parent == GRADE_LUT_DIR.resolve())
            except OSError:
                ok = False
        if not ok:
            plan.do(
                "%s on %s points at %s -- reset it to %s"
                % (GRADE_FILTER, CAM_OFF_SOURCE, path or "nothing",
                   GRADE_LUT.name),
                lambda: obs.req("SetSourceFilterSettings", {
                    "sourceName": CAM_OFF_SOURCE,
                    "filterName": GRADE_FILTER,
                    "filterSettings": {"image_path": str(GRADE_LUT)},
                }),
            )

    # Position, asserted last: a freshly created filter lands at the bottom of
    # the chain, which is the one place this one must never be.
    cur = obs.req(
        "GetSourceFilterList", {"sourceName": CAM_OFF_SOURCE})["filters"]
    idx = {f["filterName"]: f["filterIndex"] for f in cur}
    if (GRADE_FILTER in idx and CAM_OFF_FILTER in idx
            and idx[GRADE_FILTER] > idx[CAM_OFF_FILTER]):
        plan.do(
            "move %s above %s -- under it, the kill switch stops producing "
            "black" % (GRADE_FILTER, CAM_OFF_FILTER),
            lambda: obs.req("SetSourceFilterIndex", {
                "sourceName": CAM_OFF_SOURCE,
                "filterName": GRADE_FILTER,
                "filterIndex": 0,
            }),
        )


def vertical_canvas(obs):
    """The canvas that is not Main, by uuid. Never matched by name -- OBS
    accepts canvasName and then ignores it.

    A canvas outlives the plugin that drove it -- it is saved in the scene
    collection -- and an orphan reports a null base size. Swapping Aitum for
    Restream's fork left exactly that behind, first in the list, so "the one
    that isn't Main" picked a canvas nothing renders."""
    for c in obs.req("GetCanvasList")["canvases"]:
        if (not c.get("canvasFlags", {}).get("MAIN")
                and (c.get("canvasVideoSettings") or {}).get("baseWidth")):
            return c
    return None


def do_vertical(obs, plan: Plan, a, pw: str) -> None:
    """Assert VCOMIC on the vertical canvas.

    Everything here addresses the canvas by uuid and the scene by uuid, for the
    reasons in the VERT_SCENE block above. Runs after the COMIC phase because
    it reuses Game / Cam / Chat, which that phase creates.
    """
    cv = vertical_canvas(obs)
    if cv is None:
        plan.warn(
            "no second canvas exists, so there is nothing to build on. Install "
            "the Aitum Vertical Canvas plugin, restart OBS -- plugins bind at "
            "process start -- and add a canvas in its dock. --vertical does the "
            "rest."
        )
        return

    cu = cv["canvasUuid"]
    vs = cv["canvasVideoSettings"]
    if (vs["baseWidth"], vs["baseHeight"]) != (VERT_W, VERT_H):
        plan.warn(
            "vertical canvas %r is %dx%d, vertical.html assumes %dx%d -- every "
            "hole rect it pushes is in canvas pixels, so they would all be "
            "wrong. Fix it in the Aitum dock; obs-websocket has no request that "
            "can set a canvas resolution."
            % (cv["canvasName"], vs["baseWidth"], vs["baseHeight"], VERT_W, VERT_H)
        )

    def vscenes():
        return {x["sceneName"]: x["sceneUuid"]
                for x in obs.req("GetSceneList", {"canvasUuid": cu})["scenes"]}

    # --- the scene ---------------------------------------------------------
    # RENAME what the plugin already owns; do not CreateScene if it can be
    # avoided. A scene made over the websocket is real -- libobs has it and
    # GetSceneList returns it -- but the Aitum dock never learns about it. Its
    # config stores only `current_scene` and no scene list, so it enumerates
    # the canvas once at load and otherwise tracks only what its own UI made.
    # A created scene is therefore invisible in the dock, cannot be selected,
    # and so can never go on air: its sources stay inactive and the vertical
    # overlay never even boots.
    #
    # Renaming the plugin's own default scene sidesteps all of that. The uuid
    # is preserved, so it stays whatever the canvas already had on air -- which
    # for a fresh canvas is exactly the scene we want to become VCOMIC.
    have = vscenes()
    if VERT_SCENE not in have:
        spare = [n for n in have if n != VERT_SCENE]
        if len(spare) == 1:
            old = spare[0]
            plan.do(
                "rename vertical scene %r -> %s (keeps its uuid, so it stays "
                "the canvas's current scene)" % (old, VERT_SCENE),
                lambda u=have[old]: obs.req(
                    "SetSceneName", {"sceneUuid": u, "newSceneName": VERT_SCENE}),
            )
        elif not spare:
            plan.do(
                "create scene %s on %s" % (VERT_SCENE, cv["canvasName"]),
                lambda: obs.req("CreateScene",
                                {"sceneName": VERT_SCENE, "canvasUuid": cu}),
            )
            plan.warn(
                "%s had to be CREATED rather than renamed, because the canvas "
                "had no scene to rename. The Aitum dock will not list it until "
                "OBS restarts and the plugin re-enumerates the canvas."
                % VERT_SCENE
            )
        else:
            plan.warn(
                "the vertical canvas holds %d scenes (%s) and none is called %s, "
                "so there is no single obvious one to rename. Rename one to %s "
                "in the Aitum dock and re-run."
                % (len(spare), ", ".join(sorted(spare)), VERT_SCENE, VERT_SCENE)
            )
            return
        if a.check:
            # Nothing below can be checked against a scene that is not there yet.
            return
        have = vscenes()
    su = have[VERT_SCENE]

    # --- OverlayV ----------------------------------------------------------
    inputs = {i["inputName"]: i["inputKind"] for i in obs.req("GetInputList")["inputs"]}
    made = False
    for vname in ("OverlayV", "DeerV"):
        if vname not in inputs:
            plan.do(
                "create input %s (browser_source)" % vname,
                lambda n=vname: obs.req(
                    "CreateInput",
                    {"sceneUuid": su, "inputName": n,
                     "inputKind": "browser_source",
                     "inputSettings": browser_settings(n, pw),
                     "sceneItemEnabled": True},
                ),
            )
            made = True
            if not a.check:
                inputs[vname] = "browser_source"
        elif inputs[vname] != "browser_source":
            plan.warn(
                "%s exists as %s, not browser_source -- left alone. Delete it "
                "in OBS and re-run if you want this script to make it."
                % (vname, inputs[vname])
            )
    if made and a.check:
        return

    # Asserted every run, same as Overlay: a stale url, or "Shutdown source when
    # not visible" left ticked, breaks the vertical overlay in ways that look
    # like an overlay bug.
    for vname in ("OverlayV", "DeerV"):
        if inputs.get(vname) != "browser_source":
            continue
        want = browser_settings(vname, pw)
        held = obs.req("GetInputSettings", {"inputName": vname})["inputSettings"]
        diff = {k: v for k, v in want.items() if held.get(k) != v}
        # OBS omits defaults from the settings blob, so absent == the default.
        diff = {k: v for k, v in diff.items() if not (k not in held and v is False)}
        if diff:
            plan.do(
                "%s: set %s" % (vname, ", ".join(sorted(diff))),
                lambda n=vname, d=diff: obs.req(
                    "SetInputSettings", {"inputName": n, "inputSettings": d}),
            )

    # --- contents and z-order ---------------------------------------------
    items = obs.req("GetSceneItemList", {"sceneUuid": su})["sceneItems"]
    by_name = {i["sourceName"]: i for i in items}

    def add_parked(name):
        """Browser into VCOMIC off-canvas, for create_browser's reason: an
        item lands at 0,0, and vertical.html would not park it until the next
        scene change."""
        made = obs.req("CreateSceneItem", {"sceneUuid": su, "sourceName": name,
                                           "sceneItemEnabled": True})
        obs.req("SetSceneItemTransform", {"sceneUuid": su,
                                          "sceneItemId": made["sceneItemId"],
                                          "sceneItemTransform": VERT_PARK})

    for name in VERT_STACK:
        if name not in by_name and name in inputs:
            plan.do(
                "add %s to %s" % (name, VERT_SCENE),
                (lambda n=name: add_parked(n)) if name == BROWSER_SOURCE else
                (lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneUuid": su, "sourceName": n, "sceneItemEnabled": True})),
            )

    strays = sorted(set(by_name) - VERT_MANAGED)
    for name in strays:
        if a.prune:
            plan.do(
                "remove %s from %s" % (name, VERT_SCENE),
                lambda i=by_name[name]["sceneItemId"]: obs.req(
                    "RemoveSceneItem", {"sceneUuid": su, "sceneItemId": i}),
            )
        else:
            plan.warn(
                "%s sits in %s but no hole maps to it. It renders behind the "
                "vertical overlay and shows through whatever hole it happens to "
                "overlap. Re-run with --prune to remove it." % (name, VERT_SCENE)
            )

    if not a.check or all(n in by_name for n in VERT_STACK):
        items = obs.req("GetSceneItemList", {"sceneUuid": su})["sceneItems"]
        by_name = {i["sourceName"]: i for i in items}
        want_order = [n for n in VERT_STACK if n in by_name]
        have_order = [i["sourceName"] for i in
                      sorted(items, key=lambda i: i["sceneItemIndex"])
                      if i["sourceName"] in want_order]
        if have_order != want_order:
            plan.do(
                "restack %s: %s" % (VERT_SCENE, " < ".join(want_order)),
                lambda: [
                    obs.req("SetSceneItemIndex",
                            {"sceneUuid": su,
                             "sceneItemId": by_name[n]["sceneItemId"],
                             "sceneItemIndex": i})
                    for i, n in enumerate(want_order)
                ],
            )

    vertical_output_check(plan)

    # Whether VCOMIC is actually on air cannot be read back: SetCurrentProgramScene
    # refuses a non-main scene ("The specified scene is not from the main
    # canvas"), GetCurrentProgramScene ignores canvasUuid and reports Main's,
    # and none of the plugin's 14 hotkeys switches a scene. So this is reported
    # from the one thing that IS observable -- whether OverlayV has activated.
    # Renaming rather than creating the scene normally makes it moot.
    if not obs.req("GetSourceActive", {"sourceName": "OverlayV"})["videoActive"]:
        plan.warn(
            "OverlayV is not active, which means %s is not on air on the "
            "vertical canvas -- so the vertical overlay is not running at all. "
            "Select %s in the Aitum Vertical dock. This is the one step no "
            "request, vendor or hotkey can perform."
            % (VERT_SCENE, VERT_SCENE)
        )


def vertical_output_check(plan: Plan) -> None:
    """Report on the vertical canvas's own output settings. Never writes.

    Aitum keeps its outputs in its own plugin config, not in the OBS profile, so
    do_encoder cannot reach them and neither can `--export`: that file holds
    your stream key in clear text, which is reason enough for this function to
    be read-only and for the file to stay out of the repo.

    The trap worth naming is that `stream_encoder` is only consulted when
    `stream_advanced_settings` is on. With it off, Aitum picks an encoder itself
    and whatever is stored is inert -- so a config can sit there for months
    reading `ffmpeg_svt_av1` (CPU AV1) and encode on the GPU regardless, right
    up until somebody ticks Advanced.
    """
    cfg = obs_config_dir() / "plugin_config/vertical-canvas/config.json"
    try:
        doc = json.loads(cfg.read_text(errors="replace"))
    except (OSError, ValueError):
        return

    for canvas in doc.get("canvas", []):
        if (canvas.get("width"), canvas.get("height")) != (VERT_W, VERT_H):
            continue
        enc = canvas.get("stream_encoder") or ""
        if not canvas.get("stream_advanced_settings"):
            if enc in SOFTWARE_ENCODERS:
                plan.warn(
                    "the vertical canvas has %r stored as its stream encoder. It "
                    "is inert right now -- Aitum only reads it when Advanced is "
                    "ticked in its output settings -- but tick that and the "
                    "vertical output moves onto the CPU. Set it to a hardware "
                    "encoder there while you are thinking about it." % enc
                )
        elif enc in SOFTWARE_ENCODERS:
            plan.warn(
                "the vertical canvas is set to Advanced and encodes on %r, a "
                "software encoder. That is a second 1080x1920 encode on the CPU, "
                "on top of the program encode. Change it in the Aitum dock's "
                "output settings." % enc
            )


def available_encoders() -> set:
    """Video encoder IDs this OBS actually registered, read out of its own log.

    obs-websocket has no request for this. GetVersion reports requests and image
    formats; GetInputKindList reports sources. Nothing reports encoders, so the
    log is the only place OBS says which ones the hardware and the installed
    plugins gave it. It prints the list at every startup:

        Available Encoders:
          Video Encoders:
            - obs_nvenc_h264_tex (NVIDIA NVENC H.264)
            - obs_x264 (x264)
          Audio Encoders:

    Newest log first, skipping any that has no such block -- the very newest is
    often a two-line crash stub from the previous run. An empty set means "could
    not tell", never "none available", and every caller treats it that way.
    """
    logs = obs_config_dir() / "logs"
    try:
        files = sorted(logs.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return set()
    for f in files[:12]:
        found, inside = set(), False
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            body = line.split(": ", 1)[-1]
            if body.strip() == "Video Encoders:":
                inside = True
                continue
            if inside:
                stripped = body.strip()
                if stripped.startswith("- "):
                    found.add(stripped[2:].split(" (", 1)[0])
                    continue
                break
        if found:
            return found
    return set()


# Profile keys per output mode. Simple mode stores a short token, Advanced the
# encoder ID itself, which is why every read goes through resolve_encoder().
ENCODER_KEYS = {
    False: ("AdvOut", "Encoder", "RecEncoder"),       # Advanced
    True: ("SimpleOutput", "StreamEncoder", "RecEncoder"),
}


def resolve_encoder(raw: str, simple: bool) -> str:
    """Whatever the profile holds -> the canonical modern encoder ID."""
    if not raw:
        return "obs_x264"   # OBS's own default, in both modes
    if simple:
        return SIMPLE_ID.get(raw, raw)
    return DEPRECATED_ENCODERS.get(raw, raw)


def do_encoder(obs, plan: Plan, a) -> None:
    """Assert the video encoder for the stream and recording outputs.

    Two very different jobs, deliberately kept apart:

    - A deprecated ID is *renamed* on an ordinary run. jim_nvenc and
      obs_nvenc_h264_tex are the same encoder with the same settings; OBS maps
      one to the other and logs a deprecation warning per output per launch. So
      this is a repair, in the same spirit as fixing a stale browser URL.

    - Switching encoder -- x264 to NVENC, say -- is never done unasked, because
      x264 can be a deliberate choice (a second PC, a recording you want CPU
      quality for) and this script does not overwrite deliberate choices. It
      warns, and `--encoder auto` performs it. The README's new-machine
      walkthrough calls that flag out, which is what makes a fresh install end
      up on the GPU without anybody clicking through Settings -> Output.
    """
    mode = obs.req("GetProfileParameter",
                   {"parameterCategory": "Output",
                    "parameterName": "Mode"}).get("parameterValue")
    simple = (mode or "Simple").lower() != "advanced"
    cat, stream_key, rec_key = ENCODER_KEYS[simple]

    have = available_encoders()
    want = None
    if a.encoder == "auto":
        if not have:
            plan.warn(
                "--encoder auto could not read an encoder list out of OBS's "
                "log, so it cannot tell what this machine has and has changed "
                "nothing. Pick one: --encoder nvenc / qsv / amd / apple / x264."
            )
            return
        want = next((e for e in HW_PREFERENCE if e in have), None)
    elif a.encoder:
        want = ENCODER_CHOICES[a.encoder]
        if have and want not in have:
            plan.warn(
                "--encoder %s asks for %s, which this OBS did not register. It "
                "has: %s. Nothing changed."
                % (a.encoder, want, ", ".join(sorted(have)))
            )
            return

    touched = False
    for label, key in (("stream", stream_key), ("recording", rec_key)):
        raw = obs.req("GetProfileParameter",
                      {"parameterCategory": cat,
                       "parameterName": key}).get("parameterValue")
        # Whatever is there now, as a modern ID. With no --encoder that is also
        # the target: the only change an ordinary run makes is spelling.
        cur = resolve_encoder(raw, simple)
        target = want or cur
        written = SIMPLE_TOKEN.get(target, target) if simple else target

        # An unset key is OBS's default, which resolve_encoder already reports
        # as obs_x264. Writing that default back would be noise.
        if written != raw and (raw or want):
            touched = True
            plan.do(
                "%s encoder: %s -> %s%s"
                % (label, raw or "(OBS default)", written,
                   "" if want else "   deprecated ID, same encoder"),
                lambda c=cat, k=key, v=written: obs.req(
                    "SetProfileParameter",
                    {"parameterCategory": c, "parameterName": k,
                     "parameterValue": v}),
            )

        # Only when nothing was asked for. If you passed --encoder x264 you do
        # not need to be told there is a GPU in the machine.
        if not a.encoder and cur in SOFTWARE_ENCODERS and have:
            better = next((e for e in HW_PREFERENCE
                           if e in have and e not in SOFTWARE_ENCODERS), None)
            if better:
                plan.warn(
                    "%s output is on %s, a software encoder, but this machine "
                    "registered %s. The pan is a 7680x4320 CSS transform inside "
                    "CEF and Source Record adds an output per source -- the CPU "
                    "has enough to do. `--encoder auto` switches it."
                    % (label, cur, better)
                )

    if touched and not a.check:
        plan.warn(
            "OBS reads the encoder when an output starts, so this takes effect "
            "on your next Start Streaming / Start Recording. Settings -> Output "
            "may keep showing the old value until you reopen it, and the profile "
            "is written to disk when OBS quits cleanly."
        )


def preflight(plan: Plan) -> None:
    """Read-only checks for the things the websocket cannot set.

    These are not part of the scene graph, so nothing here is repaired -- but
    each one breaks the overlay in a way that looks like an overlay bug, which
    makes them worth naming before you find out live.
    """
    # Browser Source Hardware Acceleration lives in OBS's app-wide global.ini,
    # not in the profile, so there is no websocket request that can reach it.
    ini = obs_config_dir() / "global.ini"
    try:
        for line in ini.read_text(errors="replace").splitlines():
            if line.strip().lower().startswith("browserhwaccel"):
                if line.split("=", 1)[1].strip().lower() != "true":
                    plan.warn(
                        "Browser Source Hardware Acceleration is off. The pan is a "
                        "CSS transform on a 7680x4320 page; without it OBS renders "
                        "that on the CPU and the pan judders. Settings -> Advanced."
                    )
                break
    except OSError:
        pass

    # Both bridges serve the page their source loads, so a missing bridge is not
    # a degraded source -- it is an empty one until the bridge comes up. Both
    # pages retry, so starting the bridges late heals without touching OBS.
    for port, what in ((MASCOT_PORT, "the Deer source has no sprite sheet to load"),
                       (TTS_PORT, "the Tts source has no page, and chat is not read")):
        sock = socket.socket()
        sock.settimeout(0.4)
        try:
            sock.connect(("127.0.0.1", port))
        except OSError:
            plan.warn("nothing is listening on 127.0.0.1:%d, so %s. Start both "
                      "bridges with:\n        python3 start.py" % (port, what))
        finally:
            sock.close()

    for rel in ("mascot/mascot.html", "mascot/placement.json",
                "mascot/placement-vertical.json",
                "mascot/deer/manifest.json", "overlay.html", "vertical.html",
                "chat/tts.html", "chat/chat-bridge.py", "start.py"):
        if not (REPO / rel).exists():
            plan.warn("%s is missing from the repo" % rel)

    # Gitignored on purpose, so a fresh clone does not have it -- and the chat
    # bridge refuses to read anything aloud until it does.
    if not (REPO / "chat/blocklist.txt").exists():
        plan.warn("chat/blocklist.txt is missing. It is gitignored, so it does "
                  "not come with a clone: copy it from your other machine. "
                  "Until then the chat bridge will not start.")

    # The sheet the manifest names, whatever it is called.
    try:
        man = json.loads((REPO / "mascot/deer/manifest.json").read_text())
        sheet = REPO / "mascot/deer" / man.get("sheet", "")
        if not sheet.exists():
            plan.warn(
                "mascot/deer/manifest.json names %r but that file is not there. "
                "It is gitignored if it is sheet.png -- only the webp ships."
                % man.get("sheet")
            )
    except Exception:
        pass


def report(plan: Plan, a) -> None:
    if plan.actions:
        print("changes" if not plan.check else "would change")
        for x in plan.actions:
            print("  %s %s" % ("*" if plan.check else "+", x))
    else:
        print("scene collection already matches" if not plan.warnings
              else "scene collection matches")

    if plan.warnings:
        print("\nneeds a look")
        for w in plan.warnings:
            print("  ! %s" % w)

    if not plan.check and plan.actions:
        print("\nOBS does not write the scene collection to disk until it quits "
              "cleanly.\nScene Collection -> Export if you want a copy now.")

    if plan.check and plan.actions:
        sys.exit(1)


if __name__ == "__main__":
    main()
