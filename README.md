# Showcontrol
Showcontrol is a scheduler for the [SeamLess System](https://tu-studio.github.io/seamless-docs/). The backend built using python and fastapi is found in this repo, the frontend is found [here](https://github.com/tu-studio/showcontrol-frontend).



## Installation:

1. Clone Repo
2. grab yourself a copy of the font files `T-StarPRO-Medium.woff2` and `T-StarPRO-MediumItalic.woff2` and place them in `src/showcontrol/static/assets`
3. install

```
python -m venv venv
source venv/bin/activate

pip install -e .
```

4. setup configuration files (take the one in `example_configs` as a guide)
5. start the program using `showcontrol`

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
### bumping frontend in showcontrol
1. cd to the frontend repo
2. (only needs to be run once): `yarn`
3. `yarn build --outDir ../dir/to/showcontrol/src/showcontrol/static/` 



