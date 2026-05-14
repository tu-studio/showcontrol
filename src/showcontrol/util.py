from time import sleep
from pythonosc.udp_client import SimpleUDPClient
import socket


def create_udp_client(
    hostname: str, port: int, n_retries=120, sleep_time=1
) -> SimpleUDPClient:
    """Creates a pythonosc.upd_client.SimpleUDPClient for this hostname and string, retries on networking errors

    Args:
        hostname (str): hostname of the OSC Server
        port (int): port of the OSC Server
        n_retries (int, optional):  Defaults to 120.
        sleep_time (int, optional): time in seconds to sleep between attempts. Defaults to 1.

    Returns:
        SimpleUDPClient: SimpleUDPClient for the target OSC Server
    """
    local_n_retries = n_retries
    while True:
        try:
            return SimpleUDPClient(hostname, port)
        except socket.gaierror as e:
            if local_n_retries <= 0:
                raise
            else:
                print(
                    f"WARN: could not create client {hostname}:{port} with error: {e}. retrying..."
                )
                local_n_retries -= 1
                sleep(sleep_time)
