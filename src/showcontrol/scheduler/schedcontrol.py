import asyncio
from datetime import datetime, timedelta

import apscheduler
from apscheduler.schedulers import (
    SchedulerAlreadyRunningError,
    SchedulerNotRunningError,
)
from pythonosc.udp_client import SimpleUDPClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import socket
import json
import time
import logging
from .config import (
    get_main_config,
    read_schedule,
    read_tracks,
)

logFormat = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]: %(message)s"
timeFormat = "%Y-%m-%d %H:%M:%S"
# logging.basicConfig(format=logFormat, datefmt=timeFormat)
log = logging.getLogger(__name__)


class SchedControl(object):
    def __init__(self):

        config = get_main_config()
        # read track configs
        self.generate_track_list()

        # setup ports and ip for video panels
        self.video_broadcast_ip = config.video_screens.broadcast_ip
        self.video_broadcast_port = config.video_screens.video_port
        self.info_broadcast_port = config.video_screens.info_port

        self.playing = False
        self.playing_track = self.tracks["trailer"].id

        # setup reaper connection
        self.reaper = SimpleUDPClient(config.reaper.hostname, config.reaper.port)
        print(
            f"communicating with reaper at {config.reaper.hostname}:{config.reaper.port}"
        )

        # setup scheduler
        self.sched = AsyncIOScheduler()
        self.add_jobs_to_scheduler()

    def start_scheduler(self):
        try:
            self.sched.start()
        except SchedulerAlreadyRunningError:
            pass

    def stop_scheduler(self):
        try:
            self.sched.shutdown(wait=False)
        except SchedulerNotRunningError:
            pass

    def play_reaper(self, track_nr):
        """sends OSC-Messages to reaper to start playing the track with the corresponding track_nr

        Args:
            track_nr (int): index of the track to start playing
        """
        self.reaper.send_message("/region", [track_nr])
        self.reaper.send_message("/stop", [1.0])
        self.reaper.send_message("/play", [1.0])
        log.info("started track {} in reaper", track_nr)

    def send_udp_broadcast(self, command_dict: dict, port=None):
        """Sends the command in command_dict to the ip address defined in self.video_broadcast_ip
        if no port is specified, it will send the broadcast to all defined brooadcast ports

        Args:
            command_dict (dict): should follow the format {"command": [COMMAND_NAME, ARGS*]}
            port (int, optional): Port the broadcast is sent to. Defaults to None.
        """
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

    async def video_pause(self):
        try:
            await asyncio.sleep(0.05)
            self.send_udp_broadcast({"command": ["set_property", "pause", "yes"]})
        except:
            print("sending pause command failed")

    async def video_resume(self):
        try:
            await asyncio.sleep(0.1)
            self.send_udp_broadcast({"command": ["set_property", "pause", "no"]})
        except:
            print("sending play command failed")

    async def scheduler_pause(self):
        """Pauses scheduler and playback"""
        log.info("Pausing Scheduler")
        self.sched.pause()
        self.playing = False

        self.reaper.send_message("/track/1/mute", [1])
        await asyncio.sleep(0.5)
        self.reaper.send_message("/stop", [1.0])

        # Video nr 0 starts with a black screen
        await self.play_video(0, start_paused=True)

    def scheduler_resume(self):
        """Resumes the scheduler. Playback is not resumed"""
        log.info("Resuming Scheduler")
        self.reaper.send_message("/track/1/mute", [0])
        self.sched.resume()

    async def play_track(
        self,
        track_id: str,
        pause_scheduler: bool = True,
    ):
        """starts playing the track with the index track_id

        Args:
            track_id (str): id of the track to start playing. usually the name of the track
            pause_scheduler (bool, optional): set to True to pause the scheduler when explicitely playing a track. Defaults to True.
        """

        if not isinstance(track_id, str):
            print("Error: Play_track argument wasn't of type string")
            return
        try:
            track = self.tracks[track_id]
        except KeyError:
            raise KeyError("Invalid Track")
        self.playing = True
        self.playing_track = track_id
        if pause_scheduler:
            print("pausing scheduler")
            self.sched.pause()

        # unmute reaper
        self.reaper.send_message("/track/1/mute", [0])

        log.info(
            f"Play track: {track_id} (audio_index {track.audio_index}, video_index {track.video_index}"
        )

        self.play_reaper(track.audio_index)
        if track.video_index != -1:
            await self.play_video(track.video_index)

    async def play_video(self, video_index, start_paused=False):
        """Play the video with the given index on all video players, using their specified broadcast addresses

        Args:
            video_index (int): video index of the video. all video indices can be found in the track files
            start_paused (bool, optional): video players start with the video frozen on the first frame. set this to True to remain paused. Defaults to False.
        """
        try:

            # Set all video players to the correct video
            self.send_udp_broadcast({"command": ["playlist-play-index", video_index]})

            # machines are on "freeze on first frame", so the video players inside need an explicit play/unpause command.
            # start the video on the inner screens
            if not start_paused:
                await asyncio.sleep(0.03)
                self.send_udp_broadcast(
                    {"command": ["set_property", "pause", "no"], "async": True},
                    self.video_broadcast_port,
                )

        except Exception as e:
            print(
                f"Sending play video index command to {video_index} failed with error {e}."
            )

    def get_playing_track(self):
        if self.playing_track in self.tracks:
            return self.tracks[self.playing_track]
        else:
            raise KeyError("No Track is currently Playing")

    def add_jobs_to_scheduler(self):
        """Read the schedule specified in the config files, then add all jobs to the scheduler"""
        for job in read_schedule().schedule:
            if job.command != "play":
                log.warning(
                    f"could not add job from schedule: invalid command {job.command}"
                )
                continue

            self.sched.add_job(
                self.play_track,
                "cron",
                hour=job.hour,
                minute=job.minute,
                second=job.second,
                day_of_week=job.day_of_week,
                args=[
                    job.track_id,
                    False,
                ],  # first arg is track_id, second is whether scheduler should be paused
            )

    def schedule_track(self, track_id: str, in_seconds: int):
        try:
            track = self.tracks[track_id]
        except KeyError:
            raise KeyError(("track_id is invalid"))
        when = datetime.now() + timedelta(seconds=in_seconds)
        self.sched.add_job(
            self.play_track, "date", args=[track_id, False], run_date=when
        )

    def generate_track_list(self):
        """Reads the tracks directory and stores the tracks into the self.tracks dict

        Raises:
            KeyError: Raised when a track id is not unique
        """
        self.tracks = read_tracks(identifier_is_name=True)

    def get_upcoming_tracks(self, n_tracks=20):
        """Returns the next n_tracks scheduled tracks.

        Args:
            n_tracks (int, optional): Number of tracks to return. Defaults to 15.

        Returns:
            List[Tuple[str]]: Scheduled tracks as list with tuples in the format (time, title)
        """
        # get all jobs
        jobs = self.sched.get_jobs()

        # limit n_tracks to the number of available jobs
        n_tracks = min(len(jobs), n_tracks)

        # build a readable data structure out of that
        next_tracks = []
        for job in jobs[:n_tracks]:
            try:
                track = self.tracks[job.args[0]]
                next_tracks.append(
                    (job.next_run_time.strftime("%H:%M"), track.title_de)
                )
            except KeyError:
                pass

        return next_tracks

    def is_running(self) -> bool:
        return self.sched.state == apscheduler.schedulers.base.STATE_RUNNING
