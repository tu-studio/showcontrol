# Showcontrol
Showcontrol is a scheduler for the [SeamLess System](https://tu-studio.github.io/seamless-docs/). The backend built using python and fastapi is found in this repo, the frontend is found [here](https://github.com/tu-studio/showcontrol-frontend).

It remote-controls playback in REAPER using OSC messages, video playback is controlled using udp packets broadcast over the network.

It exposes an API for controlling playback and the schedule.


## Installation:

1. Clone Repo
2. if you want to use the infoviewer with the correct HuFo fonts grab yourself a copy of the font files `T-StarPRO-Medium.woff2` and `T-StarPRO-MediumItalic.woff2` and place them in `src/showcontrol/static/assets`
3. install

```
python -m venv venv
source venv/bin/activate

pip install -e .
```

4. setup configuration files (take the one in `example_configs` as a guide)
5. start the program using `showcontrol`

## configuration
The config Dir should follow this structure, the names of the block and track files are arbitrary:
```
example_config_dir
├── blockplan.yml
├── schedule.yml
├── showcontrol_config.yml
├── blocks
│   ├── block_a.yml
│   ├── block_b.yml
│   └── block_x.yml
└── tracks
    ├── track1.yml
    ├── track2.yml
    ├── track3.yml
    └── track4.yml
```

The information present in the tracks files is used for scheduling, playback and status information on the infoviewer

### create new schedule

In order to use the scheduler, first the schedule.yml file has to be created, this can be done from a blockplan containing multiple blocks using these commands:

``` bash
showcontrol_schedule_generator -c path/to/config_dir
```

if you also need a human readable schedule instead call
``` bash
showcontrol_schedule_generator -c path/to/config_dir -r path/to/where/you/want/the/readable/schedule/files
```

In the blockplan you can use a weekday as the outermost key. This way the programme for certain days can be overwritten, all other days will use the default programme

## accessing the info page
The info page is found on `http://127.0.0.1:8080/infoviewer` (when running on your local machine)

### setup REAPER remote control

- in reaper go to `options->Preferences->Control/OSC/web`
- press "add" to add a new conrol surface of mode `OSC`
- Device Name: Showcontrol or something like that
- Pattern Config:
  - select `(open config directory)`
  - copy `HufoShowControl.ReaperOSC` from this repo there
  - select `(refresh list)`
  - select `HufoShowControl`
- Mode: `Local port [receive only]`
  - local listen port: `8000`
  - local ip: ip of the pc, `0.0.0.0` should work


## Development
Showcontrol is built using FastAPI, the backend consists of the scheduler and seamless_status, which connects to an OSC-Kreuz to get the current state. Each component defines its API routes in a `router.py` file.

the scheduling is handled by APScheduler managed by the SchedControl class.

The frontend connects to the backend both using regular http requests and a websocket to get realtime updates of the current positions.

### API docs
information about the API can be found in the inbuilt docs of FastAPI. To access them run showcontrol, then access `http://127.0.0.1:8080/docs`

### bumping frontend in showcontrol
1. cd to the frontend repo
2. (only needs to be run once): `yarn`
3. `yarn build --outDir ../dir/to/showcontrol/src/showcontrol/static/` 


