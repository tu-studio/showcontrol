from pathlib import Path
from sched import scheduler
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from showcontrol.scheduler.config import TrackConfigError, find_config_files
from .seamless_status.seamless_listener import SeamlessListener
import click

from .seamless_status.ws_connection_manager import WSConnectionManager
from .seamless_status import router as status_router
from .scheduler import router as scheduler_router


@click.command(help="Start the backend of the seamless status")
@click.option(
    "-o",
    "--osc-kreuz-hostname",
    default="127.0.0.1",
    type=click.STRING,
    help="The hostname of the osc-kreuz to connect to",
)
@click.option(
    "--osc-kreuz-port",
    default=4999,
    type=click.INT,
    help="the settings port of the osc-kreuz to connect to",
)
@click.option(
    "-i",
    "--ip",
    default="0.0.0.0",
    type=click.STRING,
    help="the ip this program should listen on. needs to be accessible by the osc-kreuz",
)
@click.option(
    "-l",
    "--listener-port",
    default=55156,
    type=click.INT,
    help="the port the osc-kreuz listener listens on",
)
@click.option(
    "-p",
    "--api-port",
    default=8080,
    type=click.INT,
    help="the port the api listens on",
)
@click.option(
    "-s",
    "--n-sources",
    default=64,
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
def main(
    osc_kreuz_hostname,
    osc_kreuz_port,
    ip,
    listener_port,
    api_port,
    n_sources,
    name,
    disable_showcontrol,
):
    # osc_kreuz_ip = "130.149.23.211" # kaorutest

    # osc_kreuz_ip = "dose.ak.tu-berlin.de"
    # osc_kreuz_ip = "127.0.0.1"
    # osc_kreuz_hostname = "130.149.23.33"  # newmark#
    # osc_kreuz_ip = "3900-zg-re-01.asg"  # hufo

    # osc_kreuz_ip = "192.168.178.100"  # tengo

    try:
        find_config_files()
    except TrackConfigError:
        print("could not find tracks or schedule, scheduler will not be started!")
        disable_showcontrol = True

    status_router.seamless_listener = SeamlessListener(
        n_sources, ip, listener_port, osc_kreuz_hostname, osc_kreuz_port, name
    )

    status_router.connection_manager = WSConnectionManager(
        status_router.seamless_listener
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if status_router.seamless_listener is None:
            raise Exception("seamless listener is None, whyy")

        if not disable_showcontrol:
            scheduler_router.schedctrl.start_scheduler()
        await status_router.seamless_listener.start_listening()

        yield

        status_router.seamless_listener.unsubscribe_from_osc_kreuz()

        if not disable_showcontrol:
            scheduler_router.schedctrl.stop_scheduler()

    app = FastAPI(lifespan=lifespan)

    # include status
    app.include_router(status_router.router, tags=["status"])

    if not disable_showcontrol:
        app.include_router(scheduler_router.router, prefix="/api", tags=["scheduler"])
    # this enables serving static html files

    # app.mount(
    #     "/",
    #     StaticFiles(directory=Path(__file__).parent / "static", html=True),
    #     name="static",
    # )

    # serve the frontend
    static_path = Path(__file__).parent / "static"

    @app.get("/{path:path}")
    async def frontend_handler(path: str):
        fp = (static_path / path).resolve()
        if not fp.is_relative_to(static_path):
            raise HTTPException(404, "file not found")

        # to handle react-router singlepage apps redirect unknown paths to
        if not fp.exists() or not fp.is_file():
            fp = static_path / "index.html"
        return FileResponse(fp)

    import uvicorn

    uvicorn.run(app, host=ip, port=api_port)


if __name__ == "__main__":
    main()
