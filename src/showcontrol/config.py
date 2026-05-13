from ipaddress import ip_address
from pathlib import Path
import os
from dataclasses import dataclass
import logging
from typing import Any
from collections.abc import Callable
from pydantic import BaseModel, IPvAnyAddress, PositiveInt
import yaml


log = logging.getLogger()

default_config_file_path = Path("showcontrol")
default_config_file_locations = [
    Path(os.getcwd()) / "config",
    Path.home() / ".config" / default_config_file_path,
    Path("/etc") / default_config_file_path,
    Path("/usr/local/etc") / default_config_file_path,
    Path(os.getcwd()) / "example_config",
]


schedule_filename = "schedule.yml"
config_file_filename = "showcontrol_config.yml"
tracks_dirname = "tracks"
blocks_dirname = "blocks"

deprecated_config_strings = {
    "broadcast_ip": ["videobroadcast_ip"],
    "video_port": ["videobroadcast_port"],
    "info_port": ["videobroadcast_port"],
    "listen_ip": ["server_ip"],
    "osc_port": ["server_port"],
    "reaper_hostname": ["reaper_ip"],
}


class TrackLength(BaseModel):
    minutes: int
    seconds: int


class Track(BaseModel):
    id: str
    short_title: str = ""
    title_de: str
    title_en: str
    artist: str = ""
    audio_index: int = -1
    video_index: int = -1
    duration: TrackLength
    description: str
    description_en: str = ""


class ScheduledItem(BaseModel):
    track_id: str
    command: str
    hour: int
    minute: int
    second: int
    day_of_week: str | int


class ShowcontrolSchedule(BaseModel):
    schedule: list[ScheduledItem]


class HostConfig(BaseModel):
    port: PositiveInt
    hostname: str


class ShowcontrolConfig(BaseModel):
    ip: str
    port_osc_kreuz_listener: PositiveInt
    port_api: PositiveInt


class VideoscreenConfig(BaseModel):
    broadcast_ip: str
    video_port: PositiveInt
    info_port: PositiveInt


class Config(BaseModel):
    reaper: HostConfig = HostConfig(port=8000, hostname="127.0.0.1")
    osc_kreuz: HostConfig = HostConfig(port=4999, hostname="127.0.0.1")
    showcontrol: ShowcontrolConfig = ShowcontrolConfig(
        ip="0.0.0.0",
        port_osc_kreuz_listener=55156,
        port_api=8080,
    )
    video_screens: VideoscreenConfig = VideoscreenConfig(
        broadcast_ip="172.25.19.255", video_port=12339, info_port=12340
    )


class Block(BaseModel):
    name: str
    length: int
    track_padding: int
    tracks: list[str]


class ConfigError(Exception):
    pass


class TrackConfigError(ConfigError):
    pass


class ConfigManager:
    tried_finding_config_files = False
    config_file_path: Path | None = None
    schedule_file_path: Path | None = None
    tracks_dir: Path | None = None
    blocks_dir: Path | None = None

    def __init__(self, config_path: Path | None = None):
        self.find_config_files(config_path)

    def find_config_files(self, config_path: Path | None = None):

        if config_path is not None and not config_path.exists():
            raise ConfigError(f"config path {config_path} does not exist, exiting")

        self.tried_finding_config_files = True

        if config_path is None:
            for possible_config_path in default_config_file_locations:
                if possible_config_path.exists():
                    config_path = possible_config_path
                    break
        if config_path is None:
            print(
                f"No valid config dir found, loading defaults where possible, not loading tracks"
            )
            return
        print(f"loading config files from {config_path}")

        config_file_path = config_path / config_file_filename
        schedule_file_path = config_path / schedule_filename
        tracks_dir = config_path / tracks_dirname
        blocks_dir = config_path / blocks_dirname

        if config_file_path.exists() and config_file_path.is_file():
            self.config_file_path = config_file_path
        if schedule_file_path.exists() and schedule_file_path.is_file():
            self.schedule_file_path = schedule_file_path

        if tracks_dir.exists() and tracks_dir.is_dir():
            self.tracks_dir = tracks_dir
        if blocks_dir.exists() and blocks_dir.is_dir():
            self.blocks_dir = blocks_dir

    def read_config_file(self, config_path: Path) -> Any:
        with open(config_path) as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    # def get_config(config_path: Path | None = None) -> dict:
    #     if config_path is None:
    #         if config_paths is None:
    #             find_config_files()
    #         if config_paths is None:
    #             raise ConfigError(
    #                 "no config paths found, call find_config_files() before trying to read a config file"
    #             )
    #         config_path = config_paths.config_file_path
    #     return read_config_file(config_path)

    def get_main_config(self) -> Config:
        if config_path is None:
            if self.config_paths is None:
                self.find_config_files()
            if self.config_paths is None:
                raise ConfigError(
                    "no config paths found, call find_config_files() before trying to read a config file"
                )
            config_path = self.config_paths.config_file_path
        return Config(**read_config_file(config_path))

    # T = TypeVar("T")

    # def read_config_option(
    #     config,
    #     option_name: str,
    #     option_type: Callable[..., T] | None = None,
    #     default: T = None,
    # ) -> T:
    #     if option_name in config:
    #         pass
    #     elif option_name in deprecated_config_strings:
    #         for deprecated_option_name in deprecated_config_strings[option_name]:
    #             if deprecated_option_name in config:
    #                 log.warning(
    #                     f"option {deprecated_option_name} is deprecated, please use {option_name} instead"
    #                 )
    #                 option_name = deprecated_option_name
    #                 break
    #     else:
    #         return default

    #     val = config[option_name]

    #     if option_type is None:
    #         return val

    #     try:
    #         return option_type(val)
    #     except Exception:
    #         log.error(f"Could not read config option {option_name}, invalid type")
    #     return config[option_name]

    def read_tracks(
        track_dir: str | Path | None = None, identifier_is_name=True
    ) -> dict[str | int, Track]:
        """Reads all yaml track files in the specified directory

        Args:
            track_dir (str | Path, optional): Directory that contains the track yamls. If not specified explicitely the
            identifier_is_name (bool, optional): Specifies if the returned dict uses the names of the tracks as the outermost key. If set to False the audio_index is used instead. Defaults to True.

        Raises:
            Exception:

        Returns:
            dict: Contains all tracks
        """
        if track_dir is None:
            if config_paths is None:
                raise ConfigError(
                    "no config paths found, call find_config_files() before trying to read a config file"
                )
            track_dir = config_paths.tracks_dir

        track_dir = Path(track_dir)
        tracks = {}
        for track_file in track_dir.glob("*.yml"):
            track = Track(**read_config_file(track_file))
            if track.short_title == "":
                track.short_title = track.title_de

            identifier: str | int = (
                track.id if identifier_is_name else track.audio_index
            )

            if identifier in tracks:
                raise Exception(f"track identifier {identifier} is not unique!")

            tracks[identifier] = track

        return tracks

    def read_blocks(block_dir: Path | str | None) -> dict[str, Block]:
        if block_dir is None:
            if config_paths is None:
                raise ConfigError(
                    "no config paths found, call find_config_files() before trying to read a config file"
                )
            block_dir = config_paths.blocks_dir

        block_dir = Path(block_dir)

        blocks = {}
        for block_file in block_dir.glob("*.yml"):
            block = Block(**read_config_file(block_file))

            identifier = block.name
            if identifier in blocks:
                raise Exception(f"Block identifier {identifier} is not unique")

            blocks[identifier] = block
        return blocks

    def read_schedule(schedule_path: Path | None = None) -> ShowcontrolSchedule:
        # TODO validate
        if schedule_path is None:
            if config_paths is None:
                raise ConfigError(
                    "no config paths found, call find_config_files() before trying to read a config file"
                )
            schedule_path = config_paths.schedule_file_path

        if not (schedule_path.exists() and schedule_path.is_file()):
            raise ConfigError("No Schedule File found")

        return ShowcontrolSchedule(schedule=read_config_file(schedule_path))
