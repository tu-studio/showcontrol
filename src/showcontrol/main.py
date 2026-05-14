from pathlib import Path
from sched import scheduler
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import sys
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from showcontrol.scheduler.schedcontrol import SchedControl

from .seamless_status.seamless_listener import SeamlessListener
import click

from .seamless_status.ws_connection_manager import WSConnectionManager
from .seamless_status import router as status_router
from .scheduler import router as scheduler_router
from .config import ConfigError, ConfigManager


@click.command(help="Start the backend of the seamless status")
@click.option(
    "-o",
    "--osc-kreuz-hostname",
    default=None,
    type=click.STRING,
    help="The hostname of the osc-kreuz to connect to",
)
@click.option(
    "--osc-kreuz-port",
    default=None,
    type=click.INT,
    help="the settings port of the osc-kreuz to connect to",
)
@click.option(
    "-i",
    "--ip",
    default=None,
    type=click.STRING,
    help="the ip this program should listen on. needs to be accessible by the osc-kreuz",
)
@click.option(
    "-l",
    "--listener-port",
    default=None,
    type=click.INT,
    help="the port the osc-kreuz listener listens on",
)
@click.option(
    "-p",
    "--api-port",
    default=None,
    type=click.INT,
    help="the port the api listens on",
)
@click.option(
    "-s",
    "--n-sources",
    default=None,
    type=click.INT,
    help="the number of sources in the osc-kreuz",
)
@click.option(
    "-n",
    "--name",
    default="seamless_status",
    type=click.STRING,
    help="the name with which to register at the osc-kreuz",
)
@click.option(
    "-d",
    "--disable-showcontrol",
    is_flag=True,
    help="disables the scheduling backend of showcontrol",
    default=False,
)
@click.option(
    "-c",
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="path to config dir",
    default=None,
)
def main(
    osc_kreuz_hostname,
    osc_kreuz_port,
    ip,
    listener_port,
    api_port,
    n_sources,
    name,
    disable_showcontrol,
    config_dir,
):

    config_manager = ConfigManager(config_dir)

    if not config_manager.has_track_configs():
        print("could not find tracks or schedule, scheduler will not be started!")
        disable_showcontrol = True

    try:
        config = config_manager.get_main_config()
    except ConfigError as e:
        print(f"ERROR: {e}. Exiting...")
        sys.exit(-3)
    # override config values with cli values
    for cli_option, config_container, config_key in [
        (osc_kreuz_hostname, config.osc_kreuz, "hostname"),
        (osc_kreuz_port, config.osc_kreuz, "port"),
        (ip, config.showcontrol, "ip"),
        (listener_port, config.showcontrol, "port_osc_kreuz_listener"),
        (api_port, config.showcontrol, "port_api"),
        (n_sources, config, "n_sources"),
        (name, config, "name"),
    ]:
        if cli_option is not None:
            # TODO this is not really a nice way of handling this
            config_container.__setattr__(config_key, cli_option)

    # setup SeamlessListener and WSConnection manager and add it to status_router
    # these are being setup here, so we can use the schedule_generator without long wait times i think? that can probably be done in a better way
    status_router.seamless_listener = SeamlessListener(config)

    status_router.connection_manager = WSConnectionManager(
        status_router.seamless_listener
    )
    try:
        scheduler_router.schedctrl = SchedControl(config_manager)
    except ConfigError as e:
        print(f"ERROR: {e}. Exiting...")
        sys.exit(-3)

    # lifespan manager to start scheduler and seamless listener before starting the app, and stop them before exiting
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if status_router.seamless_listener is None:
            raise Exception("seamless listener is None, whyy")

        if not disable_showcontrol and scheduler_router.schedctrl is not None:
            scheduler_router.schedctrl.start_scheduler()
        await status_router.seamless_listener.start_listening()

        # the function pauses here and only continues when showcontrol is stopped
        yield

        status_router.seamless_listener.unsubscribe_from_osc_kreuz()

        if not disable_showcontrol and scheduler_router.schedctrl is not None:
            scheduler_router.schedctrl.stop_scheduler()

    app = FastAPI(lifespan=lifespan)

    # include api endpoints for seamless listener and system status
    app.include_router(status_router.router, tags=["status"])

    # include showcontrol api endpoints if not disabled
    if not disable_showcontrol:
        app.include_router(scheduler_router.router, prefix="/api", tags=["scheduler"])

    # serve the frontend
    static_path = Path(__file__).parent / "static"

    @app.get("/{path:path}")
    async def frontend_handler(path: str):

        # path has to be relative to the static path (otherwise one could access files from parent directories, that would be bad!)
        fp = (static_path / path).resolve()
        if not fp.is_relative_to(static_path):
            raise HTTPException(404, "file not found")

        # to handle react-router singlepage apps redirect unknown paths to index.html
        if not fp.exists() or not fp.is_file():
            fp = static_path / "index.html"
        return FileResponse(fp)

    # serve the app using uvicorn
    import uvicorn

    uvicorn.run(app, host=config.showcontrol.ip, port=config.showcontrol.port_api)


if __name__ == "__main__":
    main()
