from pathlib import Path
import sys
from typing import Any
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from apscheduler.schedulers.background import BackgroundScheduler
from threading import Thread
import yaml
import os
import socket
import json
import time
import logging
from showcontrol.config import (
    ConfigError,
    read_config,
    read_config_option,
    read_schedule,
    read_tracks,
)

log = logging.getLogger()


class SchedControl(object):
    def __init__(self):

        # read config files
        # TODO make configurable
        try:
            config_paths = read_config()
        except ConfigError as e:
            log.error(f"Error while loading config: {e}")
            sys.exit(-1)

        with open(config_paths.config_file_path) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)

        # read track configs
        self.generate_track_list(config_paths.tracks_dir)

        self.video_broadcast_ip = read_config_option(self.config, "broadcast_ip", str)
        self.video_broadcast_port = read_config_option(self.config, "video_port", int)
        self.info_broadcast_port = read_config_option(self.config, "info_port", int)

        self.listen_ip = read_config_option(self.config, "listen_ip", str, "127.0.0.1")
        self.listen_port = read_config_option(self.config, "listen_port", int, 9001)

        self.reaper_hostname = read_config_option(
            self.config, "reaper_hostname", str, "127.0.0.1"
        )
        self.reaper_port = read_config_option(self.config, "reaper_port", int, 8000)

        self.playing = False
        self.listening = False

        # setup reaper connection
        self.reaper = SimpleUDPClient(self.reaper_hostname, self.reaper_port)
        print(f"communicating with reaper at {self.reaper_hostname}:{self.reaper_port}")

        # setup osc server
        self.dispatcher = Dispatcher()
        self.setup_osc_callbacks()
        self.server = BlockingOSCUDPServer(
            (self.listen_ip, self.listen_port),
            dispatcher=self.dispatcher,
        )

        # setup scheduler
        self.sched = BackgroundScheduler()
        self.add_jobs_to_scheduler(config_paths.schedule_file_path)

    def start_listening(self):
        self.listening = True

        # start scheduler
        self.sched.start()

        # start osc server
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.start()
        print(f"listening for communication on {self.listen_ip}:{self.listen_port}")

    def stop_listening(self):
        if self.listening:
            self.server.shutdown()
            self.sched.shutdown(wait=False)
        self.listening = False

    def setup_osc_callbacks(self):
        self.dispatcher.map("/showcontrol/pause", self.pause)
        self.dispatcher.map("/showcontrol/track", self.play_track)

    def play_reaper(self, track_nr):
        """sends OSC-Messages to reaper to start playing the track with the corresponding track_nr

        Args:
            track_nr (int): index of the track to start playing
        """
        self.reaper.send_message("/region", [track_nr])
        # if playing == False:
        self.reaper.send_message("/stop", [1.0])
        self.reaper.send_message("/play", [1.0])
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
    # def play_state(self, path, *values):
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

    # method for /showcontrol/pause
    def pause(self, path, *values):
        """Pauses scheduler and playback
        OSC Callback for /showcontrol/pause
        values should contain a 1.0 to stop playback or a 0.0 to continue

        Args:
            path (Any): OSC Path for this handler, is ignored
        """
        if 1.0 in values:
            print("Pause message!")
            self.reaper.send_message("/track/1/mute", [1])
            # if playing == True:
            time.sleep(0.5)
            self.reaper.send_message("/stop", [1.0])
            print("Paused!")

            # Video nr 0 starts with a black screen
            try:
                self.send_udp_broadcast({"command": ["playlist-play-index", 0]})

            except:
                print("sending play video index command to 0 failed")

            self.sched.pause()

        elif 0.0 in values:
            print("Resumed!")
            self.reaper.send_message("/track/1/mute", [0])
            self.sched.resume()

    # method for "/showcontrol/reboot"
    # def reboot(self, path, *values):
    #     if 1.0 in values:
    #         for machine in self.config["system"]:
    #             print("Reboot {}".format(machine["name"]))
    #             os.popen(
    #                 "systemctl -H {}@{} reboot".format(machine["user"], machine["ip"])
    #             )

    def play_track(
        self,
        path,
        track_id: str,
        pause_scheduler: int | bool = True,
        *values: list[Any],
    ):
        """Starts playing the track with the index track_id
        method for "/showcontrol/track"

        Args:
            path (Any): OSC path this listens on. is ignored
            track_id (str): id of the track to start playing. usually the name of the track
        """
        pause_scheduler = bool(pause_scheduler)

        if pause_scheduler:
            print("pausing scheduler")
            self.sched.pause()
            self.reaper.send_message("/track/1/mute", [0])

        if not isinstance(track_id, str):
            # TODO maybe play the track at that index instead? would be unpredictable tho...
            print("Error: Play_track argument wasn't of type string")
            return
        track = self.tracks[track_id]

        print(
            f"Play track: {track_id} (audio_index {track['audio_index']}, video_index {track['video_index']}"
        )

        self.play_reaper(track["audio_index"])
        if "video_index" in track:
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

    def add_jobs_to_scheduler(self, config_path: Path):
        for job in read_schedule(config_path):
            if job["command"] != "play":
                print(f"Error while parsing schedule: invalid command {job['command']}")
                continue

            self.sched.add_job(
                self.play_track,
                "cron",
                hour=job["hour"],
                minute=job["minute"],
                second=job["second"],
                day_of_week=job["day_of_week"],
                args=[
                    None,
                    job["track_id"],
                    False,
                ],  # first arg is the osc path, which can be None, second is track_id, third is whether scheduler should be paused
            )

    def generate_track_list(self, track_dir: Path):
        """Reads the tracks directory and stores the tracks into the self.tracks dict

        Raises:
            KeyError: Raised when a track id is not unique
        """
        self.tracks = read_tracks(track_dir, identifier_is_name=True)

    def get_scheduled_tracks(self, n_tracks=20):
        """Returns the next n_tracks scheduled tracks.

        Args:
            n_tracks (int, optional): Number of tracks to return. Defaults to 15.

        Returns:
            List[Tuple[str]]: Scheduled tracks as list with tuples in the format (time, title)
        """
        # get all jobs
        jobs = self.sched.get_jobs()
        if len(jobs) < n_tracks:
            n_tracks = len(jobs)

        next_track_jobs = jobs[:n_tracks]

        # build a readable data structure out of that
        next_tracks = []
        for job in next_track_jobs:
            try:
                track = self.tracks[job.args[1]]
                next_tracks.append(
                    (job.next_run_time.strftime("%H:%M"), track["title"])
                )
            except KeyError:
                pass

        return next_tracks


if __name__ == "__main__":
    sched = SchedControl()
    from time import sleep

    sleep(1)
    tracks = sched.get_scheduled_tracks(150)
    print(tracks)
