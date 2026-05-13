# Showcontrol
Showcontrol is a scheduler for the [SeamLess System](https://tu-studio.github.io/seamless-docs/). The backend built using python and fastapi is found in this repo, the frontend is found [here](https://github.com/tu-studio/showcontrol-frontend).



## Installation:

1. Clone Repo
2. install

```
python -m venv venv
source venv/bin/activate

pip install -e .
```

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
### bumping frontend in showcontrol
1. cd to the frontend repo
2. (only needs to be run once): `yarn`
3. `yarn build --outDir ../dir/to/showcontrol/src/showcontrol/static/` 



