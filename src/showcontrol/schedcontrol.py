from math import pi
import sys
from oscpy.client import OSCClient
from oscpy.server import OSCThreadServer, ServerClass
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from threading import Thread
import yaml
import os
import socket
import json
import time
from pathlib import Path

from showcontrol.common import read_tracks

server = OSCThreadServer()


default_config_file_path = Path("showcontrol")
default_config_file_locations = [
    Path("/home/leto/data/projects/arbeit/akt/showcontrol/config"),  # TODO delet
    Path(os.getcwd()) / "config",
    Path.home() / ".config" / default_config_file_path,
    Path("/etc") / default_config_file_path,
    Path("/usr/local/etc") / default_config_file_path,
]

schedule_filename = Path("schedule.yml")
config_file_filename = Path("showcontrol_config.yml")
tracks_dirname = Path("tracks")


@ServerClass
class SchedControl(object):
    def __init__(self):
        global server

        # read config files
        # TODO make configurable
        for possible_config_path in default_config_file_locations:
            print(possible_config_path)
            if possible_config_path.exists():
                print(f"loading configs from {possible_config_path}")

                self.schedule_file = possible_config_path / schedule_filename
                self.config_file = possible_config_path / config_file_filename
                self.tracks_dir = possible_config_path / tracks_dirname

                if not (self.schedule_file.exists() and self.schedule_file.is_file()):
                    raise FileNotFoundError("No Schedule File found")
                if not (self.config_file.exists() and self.config_file.is_file()):
                    raise FileNotFoundError("No Config File found")
                if not (self.tracks_dir.exists() and self.tracks_dir.is_dir()):
                    raise FileNotFoundError("No tracks dir found")
                break
        else:
            print("could not find config directory, exiting...")
            sys.exit(1)
        with open(self.config_file) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)

        # read track configs
        self.generate_track_list()

        self.video_broadcast_ip = self.config["videobroadcast_ip"]
        self.video_broadcast_port = self.config["videobroadcast_port"]
        self.info_broadcast_port = self.config["infobroadcast_port"]

        self.playing = False

        # setup OSC client and server
        self.reaper = OSCClient(self.config["reaper_ip"], self.config["reaper_port"])

        server.listen(
            self.config["server_ip"], self.config["server_port"], default=True
        )

        # setup scheduler

        self.sched = BlockingScheduler()
        self.jobs = self.read_schedule()
        self.add_jobs_to_scheduler()

        self.sched_thr = Thread(target=self.sched.start)
        self.sched_thr.start()
        print("sched_control init finished")

    def play(self, track_nr):
        self.reaper.send_message(b"/region", [track_nr])
        # if playing == False:
        self.reaper.send_message(b"/stop", [1.0])
        self.reaper.send_message(b"/play", [1.0])
        print(f"started track {track_nr} in reaper")

    def send_udp_broadcast(self, command_dict: dict, port=None):
        """Sends the command in command_dict to the ip address defined in self.video_broadcast_ip
        if no port is specified, it will send the broadcast to all defined brooadcast ports

        Args:
            command_dict (dict): should follow the format {"command": [COMMAND_NAME, ARGS*]}
            port (int, optional): Port the broadcast is sent to. Defaults to None.
        """
        # command_dict.update({"async": True})
        message = json.dumps(command_dict).encode("utf-8") + b"\n"
        print(message)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if port:
            sock.sendto(message, (self.video_broadcast_ip, port))
        else:
            sock.sendto(message, (self.video_broadcast_ip, self.video_broadcast_port))
            sock.sendto(message, (self.video_broadcast_ip, self.info_broadcast_port))
        sock.close()

    # @server.address_method(b"/play")
    # def play_state(self, *values):
    #     return  # return early because we don't know how it works
    #     # TODO von wo wird das aufgerufen? die sleeps sind, damit die commands in der richtigen reihenfolge ankommen
    #     print(values[0])
    #     if values[0] == 1.0:
    #         self.playing = True
    #         try:
    #             time.sleep(0.1)
    #             self.send_udp_broadcast({"command": ["set_property", "pause", "no"]})
    #         except:
    #             print("sending play command failed")

    #     elif values[0] == 0.0:
    #         self.playing = False
    #         try:
    #             time.sleep(0.05)
    #             self.send_udp_broadcast({"command": ["set_property", "pause", "yes"]})
    #         except:
    #             print("sending pause command failed")

    @server.address_method(b"/showcontrol/pause")
    def pause(self, *values):
        if 1.0 in values:
            print("Pause message!")
            self.reaper.send_message(b"/track/1/mute", [1])
            # if playing == True:
            time.sleep(0.5)
            self.reaper.send_message(b"/stop", [1.0])
            print("Paused!")

            # Video nr 0 starts with a black screen
            try:
                self.send_udp_broadcast({"command": ["playlist-play-index", 0]})

            except:
                print("sending play video index command to 0 failed")

            self.sched.pause()

        elif 0.0 in values:
            print("Resumed!")
            self.reaper.send_message(b"/track/1/mute", [0])
            self.sched.resume()

    @server.address_method(b"/showcontrol/reboot")
    def reboot(*values):
        if 1.0 in values:
            for machine in self.config["system"]:
                print("Reboot {}".format(machine["name"]))
                os.popen(
                    "systemctl -H {}@{} reboot".format(machine["user"], machine["ip"])
                )

    @server.address_method(b"/showcontrol/track")
    def play_track(self, *values):
        self.sched.pause()
        self.reaper.send_message(b"/track/1/mute", [0])

        if isinstance(values[0], int):
            # TODO maybe play the track at that index instead? would be unpredictable tho...
            print("Play_track argument was of type int, should be string")
            return
        track_id = values[0]
        track = self.tracks[track_id]

        print(
            f"Play track: {track_id} (audio_index {track['audio_index']}, video_index {track['video_index']}"
        )

        self.play(track["audio_index"])
        self.play_video(track["video_index"])

    def play_video(self, video_index):
        try:
            # info screens (outside) receive on different port.
            # machines are on "freeze on first frame", so the video players inside need an explicit play/unpause command.

            # Set all video players to the correct video
            self.send_udp_broadcast({"command": ["playlist-play-index", video_index]})
            # start the video on the inner screens
            time.sleep(0.03)
            self.send_udp_broadcast(
                {"command": ["set_property", "pause", "no"], "async": True},
                self.video_broadcast_port,
            )

        except:
            print(f"Sending play video index command to {video_index} failed.")

    def read_schedule(self):
        with open(self.schedule_file) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            return data

    def add_jobs_to_scheduler(self):
        for job in self.jobs:
            if job["command"] == "play":
                self.sched.add_job(
                    self.play,
                    "cron",
                    hour=job["hour"],
                    minute=job["minute"],
                    second=job["second"],
                    day_of_week=job["day_of_week"],
                    args=[job["audio_index"]],
                )
            if "video_index" in job:
                self.sched.add_job(
                    self.play_video,
                    "cron",
                    hour=job["hour"],
                    minute=job["minute"],
                    second=job["second"],
                    day_of_week=job["day_of_week"],
                    args=[job["video_index"]],
                )
        # self.sched.print_jobs()

    def generate_track_list(self):
        """Reads the tracks directory and stores the tracks into the self.tracks dict

        Raises:
            KeyError: Raised when a track id is not unique
        """
        self.tracks = read_tracks(self.tracks_dir, identifier_is_name=True)

    def get_scheduled_tracks(self, n_tracks=20):
        """Returns the next n_tracks scheduled tracks.

        Args:
            n_tracks (int, optional): Number of tracks to return. Defaults to 15.

        Returns:
            List[Tuple[str]]: Scheduled tracks as list with tuples in the format (time, title)
        """
        # get all jobs
        a = self.sched.get_jobs()

        if len(a) < n_tracks:
            n_tracks = len(a)

        # filter out only play commands
        next_track_jobs = (
            t for t in a[: n_tracks * 2] if t.name == "SchedControl.play"
        )

        # build a readable data structure out of that
        next_tracks = []
        for t in next_track_jobs:
            for track_name, value in self.tracks.items():
                if value["audio_index"] == t.args[0]:
                    next_tracks.append(
                        (t.next_run_time.strftime("%H:%M"), value["title"])
                    )
                    break

        return next_tracks


if __name__ == "__main__":
    sched = SchedControl()
    from time import sleep

    sleep(1)
    tracks = sched.get_scheduled_tracks(150)
    print(tracks)
