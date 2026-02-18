# SalahNow CLI

Command-line prayer times using the same source logic as SalahNow Web:
- Türkiye: Diyanet (`ezanvakti.emushaf.net`)
- Worldwide: Muslim World League via AlAdhan (`method=3`, `school=1`)

## Install

### Option 1: pipx from PyPI (recommended)

```bash
pipx install salahnow-cli
```

### Option 2: pip from PyPI

```bash
python3 -m pip install --user salahnow-cli
```

### Option 3: local dev install

```bash
pipx install .
```

### Option 4: install script

```bash
./scripts/install.sh
```

## Commands

### Show today's prayer times

```bash
salahnow
```

Check version:

```bash
salahnow --version
```

### Next prayer + live countdown

```bash
salahnow next
```

### Configure location/method/time format

```bash
salahnow config
```

Print current config:

```bash
salahnow config --show
```

Non-interactive example:

```bash
salahnow config \
  --city "New York" \
  --country "United States" \
  --country-code US \
  --lat 40.7128 \
  --lon -74.0060 \
  --method mwl \
  --time-format 12h
```

Config file path:

```text
~/.config/salahnow/config.json
```

### Notifications daemon

```bash
salahnow notify
```

- macOS: uses `osascript`
- Linux: uses `notify-send` (if available)

### Zsh completion

Typer/click completion is built in:

```bash
salahnow --install-completion zsh
```

or print script:

```bash
salahnow --show-completion zsh
```

## Notes

- Non-Türkiye locations are forced to `mwl` source (same as web behavior).
- Türkiye locations can use Diyanet, and CLI resolves `diyanetIlceId` from nearest TR city if missing.
- The CLI stores runtime cache in `~/.cache/salahnow/prayer_cache.json` and uses cached data when APIs are temporarily unavailable.
