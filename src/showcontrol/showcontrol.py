from flask import Blueprint, render_template, request
from threading import Thread

import apscheduler
from showcontrol.schedcontrol import SchedControl
from showcontrol.auth import login_required


# from showcontrol.db import get_db
def construct_showcontrol_bluperint(schedctrl: SchedControl):
    bp = Blueprint("showcontrol", __name__)

    @bp.route("/", methods=("GET", "POST"))
    @login_required
    def showcontrol():
        if request.method == "POST":
            if "pause" in request.form:
                t = Thread(target=schedctrl.pause, args=(None, 1))
                t.start()
            if "resume" in request.form:
                t = Thread(target=schedctrl.pause, args=(None, 0))
                t.start()
        print(
            "Scheduler is running: ",
            schedctrl.sched.state != apscheduler.schedulers.base.STATE_PAUSED,
        )
        return render_template(
            "showcontrol/pause.html",
            state=(schedctrl.sched.state == apscheduler.schedulers.base.STATE_PAUSED),
            schedule=schedctrl.get_upcoming_tracks(),
        )

    @bp.route("/tracks", methods=("GET", "POST"))
    @login_required
    def web_tracks():
        if request.method == "POST":
            track = request.form.get("track")

            if track is None:
                return "No track specified", 405

            if track not in schedctrl.tracks:
                return "Track not found", 404

            schedctrl.play_track(path=None, track_id=track)

        # Sort track keys by audio index
        sorted_track_keys = sorted(
            schedctrl.tracks.keys(), key=lambda x: schedctrl.tracks[x]["audio_index"]
        )
        # passing keys as a list is needed in the rendering to specify an order of the tracks
        return render_template(
            "showcontrol/tracks.html",
            tracks=schedctrl.tracks,
            track_keys=sorted_track_keys,
        )

    return bp
