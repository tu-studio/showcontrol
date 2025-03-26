import os

from flask import Flask
from xdg import xdg_state_home

from showcontrol.config import find_config_files, get_config, read_config_option
from showcontrol.schedcontrol import SchedControl
from .showcontrol import construct_showcontrol_bluperint
from pathlib import Path
import atexit
import click


def create_app(config_dir: Path | None = None, test_config=None) -> Flask:
    # create and configure the app
    app = Flask(
        __name__,
        instance_path=os.path.join(xdg_state_home(), "showcontrol"),
        instance_relative_config=True,
    )
    app.config.from_mapping(
        SECRET_KEY="dev",
        # SERVER_NAME='127.0.0.1:8080',
        DATABASE=os.path.join(app.instance_path, "showcontrol.sqlite"),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import db

    db.init_app(app)
    #    if not os.path.isfile(os.path.join(app.instance_path, 'webcontrol.sqlite')):
    #        db.init_db()

    find_config_files(config_dir)
    # config = get_config()
    schedctrl = SchedControl()

    schedctrl.start_listening()

    from . import auth

    app.register_blueprint(auth.bp)

    app.register_blueprint(construct_showcontrol_bluperint(schedctrl))
    app.add_url_rule("/", endpoint="index")
    app.add_url_rule("/tracks", endpoint="tracks")

    atexit.register(schedctrl.stop_listening)

    return app


@click.command()
@click.option(
    "-c",
    "--config-dir",
    "config_dir",
    type=click.Path(
        exists=True, dir_okay=True, file_okay=False, resolve_path=True, path_type=Path
    ),
    help="path to configfile",
)
@click.option("-d", "--dev", is_flag=True, help="enable flask dev mode")
@click.version_option()
def run(config_dir: Path | None, dev):

    app = create_app(config_dir=config_dir)

    """can be used to run this app, recommended way is `flask --app showcontrol.app run`"""
    # global app

    config = get_config()
    app.run(
        host=read_config_option(config, "listen_ip", str, "127.0.0.1"),
        port=read_config_option(config, "http_port", int, 8080),
        debug=dev,
    )

    # TODO find better way to run this
    atexit._run_exitfuncs()
    # schedctrl.stop_listening()
