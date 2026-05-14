import sys
from typing import Any
import yaml
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

import click

from ..config import ConfigError, ConfigManager, ConfigError

log = logging.getLogger()

day_numbers = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

time_start = datetime(2022, 2, 1, 10, 45, 0)
time_stop = datetime(2022, 2, 1, 18, 30, 0)


day_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def create_alternative_schedule(input_file, output_file, config_manager: ConfigManager):
    tracks = config_manager.read_tracks(identifier_is_name=True)
    schedule = config_manager.read_schedule(input_file).schedule

    runtimes: dict[str, Any] = {}
    # prepare track dicts by adding empty runtime dicts
    for t in tracks.values():
        runtimes[t.id] = {}

    # populate runtime dicts by adding all occurances from the schedule file to them
    for e in schedule:
        idx = e.track_id
        day_of_week = e.day_of_week
        time = f"{e.hour:02}:{e.minute:02}"

        if day_of_week not in runtimes[idx]:
            runtimes[idx][day_of_week] = []
        runtimes[idx][day_of_week].append(time)

    # write schedule to file
    with open(output_file, "w") as f:
        for t in tracks.values():
            # write track title
            f.write(t.short_title + "\n")

            for day_nrs, times in runtimes[t.id].items():
                # convert day_nrs to human readable format
                if isinstance(day_nrs, str):
                    day_nrs = day_nrs.split(",")
                    days = ",".join([day_names[int(d)] for d in day_nrs])
                else:
                    days = day_names[day_nrs]

                playtimes = ", ".join(times)
                f.write(f"\t{days:<20}\t{playtimes}\n")
            f.write("\n")


def create_readable_txt(input_file, output_file, config_manager: ConfigManager):
    track_dict = config_manager.read_tracks(identifier_is_name=False)
    with open(input_file, "r") as f:
        schedule = yaml.safe_load(f)

    # make sure output file is not a directory, append .txt to the output filename if it has no file ending
    if os.path.isdir(output_file):
        output_file = os.path.join(output_file, "schedule_readable.txt")
    else:
        fn, fe = os.path.splitext(output_file)
        if not fe:
            output_file = output_file + ".txt"

    with open(output_file, "w") as outfile:
        for scheduled_item in schedule:
            # convert day numbers to names
            # if there is only one day, it is already an integer
            day_nrs = scheduled_item["day_of_week"]
            if isinstance(day_nrs, str):
                day_nrs = day_nrs.split(",")
                days = ",".join([day_names[int(d)] for d in day_nrs])
            else:
                days = day_names[day_nrs]

            timestr = f"{scheduled_item['hour']:02}:{scheduled_item['minute']:02}:{scheduled_item['second']:02}"

            idx = scheduled_item["audio_index"]
            if idx in track_dict:
                track_title = track_dict[idx].id
                outfile.write(f"{days:<20}\t{timestr}\t{track_title}\n")
            else:
                print(f"index {idx} missing from track_dict")
                outfile.write(timestr + "\n")
    outfile.close()
    print("Program Schedule points", len(schedule))
    print("written programfile to", output_file)


def writeEntry(
    file,
    hour,
    minute,
    secs,
    audio_idx,
    video_idx,
    track_name: str,
    days=[0, 1, 2, 3, 4, 5, 6],
):
    days = [str(d) for d in days]
    file.write(
        f"- track_id: {track_name}\n"
        f"  audio_index: {audio_idx} # included for compatibility \n"
        f"  video_index: {video_idx}  # included for compatibility \n"
        f"  command: play\n"
        f"  day_of_week: {','.join(days)}\n"
        f"  hour: {hour}\n"
        f"  minute: {minute}\n"
        f"  second: {secs}\n"
    )


def round_up_time(timestamp: datetime, round_to_minutes=5):
    delta = timedelta(minutes=round_to_minutes)
    return timestamp + (datetime.min - timestamp) % delta


def create_schedule(config_manager: ConfigManager, output_file):
    # load tracks
    try:
        tracks = config_manager.read_tracks()
    except ConfigError as e:
        print(f"ERROR: {e}. Exiting...")
        sys.exit(-1)
    print("\n".join([t.short_title for t in tracks.values()]))
    # load blocks
    try:
        blocks = config_manager.read_blocks()
    except ConfigError as e:
        print(f"ERROR: {e}. Exiting...")
        sys.exit(-1)

    # load block plan
    with open(config_manager.config_file_path.parent / "blockplan.yml") as f:
        blockplan = yaml.load(f, Loader=yaml.FullLoader)

    # find days with explicit schedules
    days_explicit_schedule = set(blockplan.keys()) - set(["default"])

    # get the differnce of the set of all day numbers and the days with an
    # explicit schedule to find the days for which the
    # default schedule will be applied
    days_default_schedule = set(day_numbers.keys()) - days_explicit_schedule
    day_numbers_default = [day_numbers[d] for d in days_default_schedule]
    day_numbers_default.sort()
    with open(output_file, "w") as out_file:
        # iterate over all days (including "default")
        for day in blockplan:
            logging.info(f"building schedule for day {day}")
            day_over = False

            # get the daynumbers for the default block plan
            if day == "default":
                days = day_numbers_default
                logging.info(
                    f"default schedule on days {', '.join(days_default_schedule)}"
                )
            else:
                days = [day_numbers[day]]

            blockstart = time_start

            # iterate over all blocks on a certain day
            for blockname in blockplan[day]["blocks"]:
                block = blocks[blockname]

                trackstart = blockstart

                if day_over:
                    break

                # iterate over all tracks in a block
                for track_name in block.tracks:
                    if trackstart >= time_stop:
                        day_over = True
                        break
                    track = tracks[track_name]

                    writeEntry(
                        out_file,
                        trackstart.hour,
                        trackstart.minute,
                        trackstart.second,
                        track.audio_index,
                        track.video_index,
                        track_name,
                        days,
                    )

                    trackstart = round_up_time(
                        trackstart
                        + timedelta(
                            minutes=track.duration.minutes,
                            seconds=track.duration.seconds,
                        )
                        + timedelta(seconds=block.track_padding)
                    )
                blockstart = trackstart


@click.command(help="generate schedules for showcontrol")
@click.option(
    "-c",
    "--config-dir",
    type=click.Path(
        exists=True, dir_okay=True, resolve_path=True, path_type=Path, file_okay=False
    ),
    help="path to directory with config files",
    default=Path(__file__).parent.parent.parent / "config",
)
@click.option(
    "-o",
    "--output-file",
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path, file_okay=True),
    default=Path("schedule.yml"),
)
@click.option(
    "-r",
    "--readable-schedule-dir",
    type=click.Path(
        exists=True, dir_okay=True, resolve_path=True, path_type=Path, file_okay=False
    ),
    help="path to where the readable schedules should be saved",
    default=None,
)
def main(config_dir: Path, output_file: Path, readable_schedule_dir: Path | None):
    config_manager = ConfigManager(config_dir)
    create_schedule(config_manager, output_file)
    today = datetime.now().strftime("%Y-%m-%d")

    if readable_schedule_dir is None:
        return

    create_readable_txt(
        output_file,
        readable_schedule_dir / f"hufoprogram_{today}_full_schedule.txt",
        config_manager,
    )
    create_alternative_schedule(
        output_file,
        readable_schedule_dir / f"hufoprogram_{today}_track_schedule.txt",
        config_manager,
    )


if __name__ == "__main__":
    main()
