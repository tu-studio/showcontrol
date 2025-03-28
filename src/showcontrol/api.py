from flask import Blueprint, request
import apscheduler

from showcontrol.schedcontrol import SchedControl


def construct_api_blueprint(schedctrl: SchedControl) -> Blueprint:
    bp = Blueprint("api", __name__)

    @bp.route("tracks")
    def get_tracks():
        return sorted(
            schedctrl.tracks.values(), key=lambda x: x["audio_index"]
        )

    @bp.route("scheduler_state", methods=["GET", "POST", "PUT"])
    def get_scheduler_state():

        # handle state changing on put or post
        if request.method in ["PUT", "POST"]:
            if (state := request.args.get("state")) == "paused":
                schedctrl.scheduler_pause()
            elif state == "running":
                schedctrl.scheduler_resume()
            else:
                return "bad request!", 400

        scheduler_state = {"state": ("running" if schedctrl.is_running() else "paused")}
        return scheduler_state

    @bp.route("upcoming_tracks")
    def get_upcoming_tracks():
        n_tracks = request.args.get("n_tracks", 20, int)
        return schedctrl.get_upcoming_tracks(n_tracks)

    @bp.route("play_track", methods=["PUT", "POST"])
    def play_track():
        track_id = request.args.get("track_id", "", str)
        try:
            schedctrl.play_track(track_id)
        except KeyError:
            return "invalid track name", 404

        return track_id

    @bp.route("schedule_track", methods=["PUT", "POST"])
    def schedule_track():
        track_id = request.args.get("track_id", "", str)
        interval = request.args.get("interval", 10, int)

        try:
            schedctrl.schedule_track(track_id, interval)
        except KeyError:
            return "invalid track name", 404
        return track_id

    return bp
