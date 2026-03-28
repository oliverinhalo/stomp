# Stomp — Guitar Tab Manager

Stomp is a Python GUI app for browsing Ultimate Guitar tabs, saving downloaded versions locally, and navigating song text with a pedal-style interface.

## Features

- Search Ultimate Guitar and download tab content
- View saved songs and song versions
- Page-based song view with zoom controls
- Global default zoom setting in the main menu
- Save downloaded songs only when explicitly requested
- Keyboard and GPIO pedal support
- Full-screen display mode

## Requirements

- Python 3.11+ recommended
- `tkinter` installed on your system
- `curl` is optional but improves Ultimate Guitar fetch reliability

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

For keyboard-only mode (no GPIO pedals):

```bash
python main.py --no-gpio
```

## Controls

- `left` / `right` pedals or arrow keys: navigate menus
- `middle` pedal: select
- `hold middle`: back / return / unlock
- `left + middle`: previous page in song view
- `right + middle`: next page in song view
- `U` key: unlock from standby
- `Escape`: go back one screen instead of closing

## Settings

Open `Settings` from the main menu to set the default zoom level for new songs and downloads.

## Notes

- Songs are only saved to disk when you choose `Save` from the edit menu.
- Global config is stored in `app/config.json`.
