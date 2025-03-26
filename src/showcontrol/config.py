from pathlib import Path
import os
from dataclasses import dataclass
import logging
from typing import TypeVar
from collections.abc import Callable
import yaml


log = logging.getLogger()

default_config_file_path = Path("showcontrol")
default_config_file_locations = [
    Path(os.getcwd()) / "config",
    Path.home() / ".config" / default_config_file_path,
    Path("/etc") / default_config_file_path,
    Path("/usr/local/etc") / default_config_file_path,
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


class ConfigError(Exception):
    pass


@dataclass
class ConfigPaths:
    config_file_path: Path
    schedule_file_path: Path
    tracks_dir: Path
    blocks_dir: Path


config_paths: ConfigPaths | None = None


def find_config_files(config_path: Path | None = None) -> ConfigPaths:
    if config_path is not None and not config_path.exists():
        raise ConfigError(f"config path {config_path} does not exist, exiting")

    if config_path is None:
        for possible_config_path in default_config_file_locations:
            if possible_config_path.exists():
                config_path = possible_config_path
                break
    if config_path is None:
        # TODO load default?
        raise ConfigError(f"No valid config dir found")
    print(f"loading config files from {config_path}")

    paths = ConfigPaths(
        config_path / config_file_filename,
        config_path / schedule_filename,
        config_path / tracks_dirname,
        config_path / blocks_dirname,
    )

    if not (paths.config_file_path.exists() and paths.config_file_path.is_file()):
        raise ConfigError("No Config File found")
    if not (paths.tracks_dir.exists() and paths.tracks_dir.is_dir()):
        raise ConfigError("No tracks dir found")

    global config_paths
    config_paths = paths
    return paths


def read_config_file(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_config(config_path: Path | None = None) -> dict:
    if config_path is None:
        if config_paths is None:
            raise ConfigError(
                "no config paths found, call find_config_files() before trying to read a config file"
            )
        config_path = config_paths.config_file_path
    return read_config_file(config_path)


T = TypeVar("T")


def read_config_option(
    config,
    option_name: str,
    option_type: Callable[..., T] | None = None,
    default: T = None,
) -> T:
    if option_name in config:
        pass
    elif option_name in deprecated_config_strings:
        for deprecated_option_name in deprecated_config_strings[option_name]:
            if deprecated_option_name in config:
                log.warning(
                    f"option {deprecated_option_name} is deprecated, please use {option_name} instead"
                )
                option_name = deprecated_option_name
                break
    else:
        return default

    val = config[option_name]

    if option_type is None:
        return val

    try:
        return option_type(val)
    except Exception:
        log.error(f"Could not read config option {option_name}, invalid type")
    return config[option_name]


def read_tracks(track_dir: str | Path | None = None, identifier_is_name=True) -> dict:
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
        track = read_config_file(track_file)

        if identifier_is_name:
            identifier = track["name"]
        else:
            identifier = track["audio_index"]

        if identifier in tracks:
            raise Exception(f"track identifier {identifier} is not unique!")

        tracks[identifier] = track

    return tracks


def read_blocks(block_dir: Path | str | None) -> dict:
    if block_dir is None:
        if config_paths is None:
            raise ConfigError(
                "no config paths found, call find_config_files() before trying to read a config file"
            )
        block_dir = config_paths.blocks_dir

    block_dir = Path(block_dir)

    blocks = {}
    for block_file in block_dir.glob("*.yml"):
        block = read_config_file(block_file)

        identifier = block["name"]
        if identifier in blocks:
            raise Exception(f"Block identifier {identifier} is not unique")

        blocks[identifier] = block
    return blocks


def read_schedule(schedule_path: Path | None = None) -> dict:
    # TODO validate
    if schedule_path is None:
        if config_paths is None:
            raise ConfigError(
                "no config paths found, call find_config_files() before trying to read a config file"
            )
        schedule_path = config_paths.schedule_file_path

    if not (schedule_path.exists() and schedule_path.is_file()):
        raise ConfigError("No Schedule File found")
    return read_config_file(schedule_path)
