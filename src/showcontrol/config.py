from ipaddress import ip_address
from pathlib import Path
import os
from dataclasses import dataclass
import logging
from typing import Any
from collections.abc import Callable
from pydantic import BaseModel, PositiveInt
from pydantic_core import ValidationError
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
    name: str = "seamless_status"
    n_sources: int = 32
    reaper: HostConfig = HostConfig(port=8000, hostname="127.0.0.1")
    osc_kreuz: HostConfig = HostConfig(port=4999, hostname="127.0.0.1")
    showcontrol: ShowcontrolConfig = ShowcontrolConfig(
        ip="0.0.0.0",
        port_osc_kreuz_listener=55156,
        port_api=8080,
    )
    video_screens: VideoscreenConfig = VideoscreenConfig(
        broadcast_ip="10.30.70.255", video_port=12339, info_port=12340
    )


class Block(BaseModel):
    name: str
    length: int
    track_padding: int
    tracks: list[str]


class ConfigError(Exception):
    pass


class ConfigManager:
    config_file_path: Path | None = None
    schedule_file_path: Path | None = None
    tracks_dir: Path | None = None
    blocks_dir: Path | None = None

    def __init__(self, config_path: Path | None = None):
        self.find_config_files(config_path)

    def find_config_files(self, config_path: Path | None = None):

        if config_path is not None and not config_path.exists():
            raise ConfigError(f"config path {config_path} does not exist, exiting")

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

    def get_main_config(self) -> Config:
        """Returns the main config. First loads it either from file or defaults if it has not been loaded yet.

        Raises:
            ConfigError: raised when the config is faulty

        Returns:
            Config: main config file
        """
        try:
            return self.config
        except AttributeError:
            # read main config
            if self.config_file_path is not None:
                try:
                    self.config = Config(**self.read_config_file(self.config_file_path))
                except ValidationError as e:
                    print_validation_error(self.config_file_path, e)
                    raise ConfigError("failed to load main config")
            else:
                self.config = Config()
            return self.config

    def has_track_configs(self) -> bool:
        return self.schedule_file_path is not None and self.tracks_dir is not None

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
        self, track_dir: str | Path | None = None, identifier_is_name=True
    ) -> dict[str | int, Track]:
        """Reads all yaml track files in the specified directory

        Args:
            track_dir (str | Path, optional): Directory that contains the track yamls. If not specified explicitely the
            identifier_is_name (bool, optional): Specifies if the returned dict uses the names of the tracks as the outermost key. If set to False the audio_index is used instead. Defaults to True.

        Raises:
            ConfigError:

        Returns:
            dict: Contains all tracks
        """
        if track_dir is None:
            if self.tracks_dir is None:
                raise ConfigError("no track config found")
            track_dir = self.tracks_dir

        track_dir = Path(track_dir)
        tracks = {}
        for track_file in track_dir.glob("*.yml"):
            try:
                track = Track(**self.read_config_file(track_file))
            except ValidationError as e:
                print_validation_error(track_file, e)
                raise ConfigError("failed to load track")
            if track.short_title == "":
                track.short_title = track.title_de

            identifier: str | int = (
                track.id if identifier_is_name else track.audio_index
            )

            if identifier in tracks:
                raise ConfigError(f"track identifier {identifier} is not unique!")

            tracks[identifier] = track

        return tracks

    def read_blocks(self, block_dir: Path | str | None = None) -> dict[str, Block]:
        if block_dir is None:
            if self.blocks_dir is None:
                raise ConfigError("no blocks config found")
            block_dir = self.blocks_dir

        block_dir = Path(block_dir)

        blocks = {}
        for block_file in block_dir.glob("*.yml"):
            try:
                block = Block(**self.read_config_file(block_file))
            except ValidationError as e:
                print_validation_error(block_file, e)
                raise ConfigError("failed to load block")

            identifier = block.name
            if identifier in blocks:
                raise Exception(f"Block identifier {identifier} is not unique")

            blocks[identifier] = block
        return blocks

    def read_schedule(self, schedule_path: Path | None = None) -> ShowcontrolSchedule:

        if schedule_path is None:
            if self.schedule_file_path is None:
                raise ConfigError("no config paths found")
            schedule_path = self.schedule_file_path

        if not (schedule_path.exists() and schedule_path.is_file()):
            raise ConfigError("No Schedule File found")

        try:
            return ShowcontrolSchedule(schedule=self.read_config_file(schedule_path))
        except ValidationError as e:
            print_validation_error(schedule_path, e)
            raise ConfigError("failed to load track")


def print_validation_error(path: Path, e: ValidationError):
    print(f"ERROR: failed to load file {path}")
    # print the errors with this config file
    for error in e.errors(
        include_url=False, include_context=False, include_input=False
    ):
        try:
            problems = ", ".join([str(x) for x in error["loc"]])
            print(f"\t{problems}: {error["msg"]}")
        except:
            pass
