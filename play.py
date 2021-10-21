from __future__ import annotations

import csv
import os
import threading
import time
import winsound as ws
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from typing import Union

import jsons
import requests
import vlc

VOLUME_LIMITS = (0, 250)  # %

# Time for a request to be considered 'long'.
LONG_THRESHOLD = 30  # seconds

FREQ_LONG = 512  # hz; server took a long time to respond.
FREQ_UNK = 2048  # server responded with an error.
FREQ_WARN = 1024
FREQ_ERR = 4096

# Tones are not distinguishable below this many milliseconds.
MIN_COUNT = 25


@dataclass
class GraylogResult:
    count: int
    count_error: int
    count_warn: int


@dataclass
class RawGraylogConfig:
    host: str
    apiToken: Union[str, None]
    requestedBy: Union[str, None]
    streams: list[str]
    mean: int


@dataclass
class RawConfig:
    soundFile: str
    pollInterval: int
    graylog: RawGraylogConfig


@dataclass
class GraylogConfig:
    host: str
    auth: tuple[str, str]
    headers: dict[str, str]
    body: dict[str, Union[str, dict[str, Union[str, int]], list[str]]]
    mean: int


@dataclass
class Config:
    sound_file: str
    poll_interval: int
    graylog: GraylogConfig


@lru_cache(None)
def _get_config() -> Config:

    config_path = os.environ.get('AURA_CONFIG', 'config.json')
    with open(config_path, 'r') as fp:
        config: RawConfig = jsons.loads(fp.read(), cls=RawConfig)

    return Config(
        sound_file=config.soundFile,
        poll_interval=config.pollInterval,
        graylog=GraylogConfig(
            host=config.graylog.host,
            auth=(
                config.graylog.apiToken or
                os.environ.get('GRAYLOG_API_TOKEN', str()),
                'token'
            ),
            headers={
                'X-Requested-By': config.graylog.requestedBy or
                os.environ.get('GRAYLOG_REQ_BY', str()),
                'Content-Type': 'application/json',
                'Accept': 'text/csv'
            },
            body={
                "streams": config.graylog.streams,
                "timerange": {
                    "type": "relative",
                    "range": 300
                },
                "fields_in_order": ["level"]
            },
            mean=config.graylog.mean
        )
    )


def _get_volume_target(gl_result: GraylogResult) -> int:
    """Find the target volume and limit based on VOLUME_LIMITS"""
    t = int((gl_result.count / _get_config().graylog.mean)*50)
    return min(max(VOLUME_LIMITS[0], t), VOLUME_LIMITS[1])


def _graylog_csv_to_levels(io: StringIO) -> list[int]:
    levels = list()
    for v in csv.DictReader(io):
        # Record anomalies as errors.
        levels.append(int(v.get('level', 0)))
    return levels


def step_try_replay(p: vlc.MediaPlayer) -> bool:
    """Returns True if player restarted, otherwise False"""
    result = bool()
    if p.get_state() == vlc.State.Ended:
        p.stop()
        p.set_time(0)
        result = p.play() == 0
    return result


def step_query_graylog() -> GraylogResult:

    # Allow exceptions to propagate. We want to know if the connection is wonky.
    resp = requests.request(
        'POST', f'http://{_get_config().graylog.host}:9000/api/views/search/messages',
        headers=_get_config().graylog.headers,
        auth=_get_config().graylog.auth,
        json=_get_config().graylog.body
    )

    if resp.status_code != 200:
        return GraylogResult(-1, 0, 0)

    csv = resp.content.decode('latin1')
    levels = _graylog_csv_to_levels(StringIO(csv))
    return GraylogResult(
        len(levels),
        len([i for i in levels if i < 4]),
        len([i for i in levels if i == 4])
    )


def step_slide_volume(p: vlc.MediaPlayer, t: int) -> None:

    last = p.audio_get_volume()
    pos = (diff := last - t) > 0
    if diff == 0:
        return

    # Aim to be at new [t]arget volume within 1s.
    for i in range(1, abs(diff), abs(int(diff/10)) or 1):
        new = last - i if pos else last + i
        p.audio_set_volume(new)
        time.sleep(0.1)


def main() -> None:

    player = vlc.MediaPlayer(_get_config().sound_file)
    player.audio_set_volume(50)
    player.play()

    interval = _get_config().poll_interval
    while True:

        print(f'Zzz... ({interval}s)')
        time.sleep(interval)
        print('-'*30)

        print('Tape rewound') if step_try_replay(player) else ...

        _st = time.time()
        print(f'Querying Graylog...', end='\r')

        # No point in threading this: one request → one response.
        gl_result = step_query_graylog()

        _ts = time.time()
        wait = round(_ts-_st, 2)
        # 'Querying Graylog... {n}s'
        print(f'Querying Graylog... {wait}s')

        target_volume = _get_volume_target(gl_result)

        # We cannot use multiprocessing because we need a shared address space.
        # We should not run this synchronously because the timing is known and
        # it returns nothing.
        threading\
            .Thread(target=step_slide_volume, args=(player, target_volume))\
            .start()

        if wait > 30:
            ws.Beep(FREQ_LONG, 1000)
        if gl_result.count == -1:
            ws.Beep(FREQ_UNK, 1000)
        else:
            if gl_result.count_error >= MIN_COUNT:
                ws.Beep(FREQ_ERR, gl_result.count_error)
            if gl_result.count_warn >= MIN_COUNT:
                ws.Beep(FREQ_WARN, gl_result.count_warn)

        # '{total} / {warn} / {err} (vol%)'
        print(gl_result.count, gl_result.count_warn,
              gl_result.count_error, sep=' / ', end='')
        print(f' ({target_volume}%) ')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
