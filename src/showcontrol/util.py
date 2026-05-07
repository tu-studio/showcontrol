from time import sleep
from pythonosc.udp_client import SimpleUDPClient
import socket


def create_udp_client(hostname: str, port: int, n_retries=120, sleep_time=1):
    while True:
        try:
            return SimpleUDPClient(hostname, port)
        except socket.gaierror as e:
            if n_retries <= 0:
                raise
            else:
                print(
                    f"WARN: could not create client {hostname}:{port} with error: {e}. retrying..."
                )
                n_retries -= 1
                sleep(1)
