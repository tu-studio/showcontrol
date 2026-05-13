from enum import Enum
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .schedcontrol import SchedControl
from .config import Track


router = APIRouter()

schedctrl = SchedControl()


@router.get("/tracks")
async def get_tracks() -> list[Track]:
    return sorted(schedctrl.tracks.values(), key=lambda x: x.audio_index)


@router.get("/track")
async def get_track(track_id: str) -> Track:
    try:
        return schedctrl.tracks[track_id]
    except KeyError:
        raise HTTPException(404, "Track not found")


class SchedulerState(str, Enum):
    paused = "paused"
    playing = "running"


@router.post("/scheduler_state")
# @router.put("scheduler_state")
async def set_scheduler_state(state: SchedulerState) -> SchedulerState:
    if state == SchedulerState.paused:
        await schedctrl.scheduler_pause()
    else:
        schedctrl.scheduler_resume()
    return SchedulerState.playing if schedctrl.is_running() else SchedulerState.paused


@router.get("/scheduler_state")
async def get_scheduler_state():

    return {
        "state": (
            SchedulerState.playing if schedctrl.is_running() else SchedulerState.paused
        )
    }


@router.get("/upcoming_tracks")
async def get_upcoming_tracks(n_tracks: int = 20):
    return schedctrl.get_upcoming_tracks(n_tracks)


@router.get("/playing_track")
async def get_playing_track() -> Track:
    return schedctrl.get_playing_track()


@router.post("/play_track")
async def play_track(track_id: str):
    try:
        await schedctrl.play_track(track_id)
    except KeyError:
        return "invalid track name", 404

    return track_id


@router.post("/schedule_track")
async def schedule_track(track_id: str, interval: int):

    try:
        schedctrl.schedule_track(track_id, interval)
    except KeyError:
        return "invalid track name", 404
    return track_id
