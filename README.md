## Installation:

1. Clone Repo
2. install and init db

```
python -m venv venv
source venv/bin/activate

pip install -e .
flask --app showcontrol.app init-db
```

## setup REAPER remote control

- in reaper go to `options->Preferences->Control/OSC/web`
- press "add" to add a new conrol surface of mode `OSC`
- Device Name: Showcontrol or something like that
- Pattern Config:
  - select `(open config directory)`
  - copy `HufoShowControl.ReaperOSC` from the Showcontrol repo there
  - select `(refresh list)`
  - select `HufoShowControl`
- Mode: `Local port [receive only]`
  - local listen port: `8000`
  - local ip: ip of the pc, `0.0.0.0` should work

## repo setup

### `schedcontrol.py`

contains the actual scheduler, the rest is for the frontend
