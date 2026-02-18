from __future__ import annotations

import json
import time
from typing import Any, Optional

import typer
from rich.console import Console
from rich.live import Live

from . import __version__
from .config import CONFIG_PATH, Config, load_config, save_config
from .location import detect_location_from_ip, search_locations
from .models import Location, PrayerSource, TimeFormat
from .notify import run_notify_daemon
from .output import build_next_panel, render_today
from .prayer_api import PrayerApiError, fetch_prayer_bundle
from .prayer_logic import get_current_prayer_info

app = typer.Typer(
    help="SalahNow CLI",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=True,
)
console = Console()


def _validate_source(value: str) -> PrayerSource:
    if value not in ("diyanet", "mwl"):
        raise typer.BadParameter("method must be either 'diyanet' or 'mwl'")
    return value  # type: ignore[return-value]


def _validate_time_format(value: str) -> TimeFormat:
    if value not in ("12h", "24h"):
        raise typer.BadParameter("time format must be either '12h' or '24h'")
    return value  # type: ignore[return-value]


def _prompt_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        value = typer.prompt(f"{prompt} [{'/'.join(choices)}]", default=default)
        if value in choices:
            return value
        console.print(f"[red]Invalid choice:[/red] {value}")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"salahnow-cli {__version__}")
        raise typer.Exit()


def _validate_coordinates(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise typer.BadParameter("latitude must be between -90 and 90")
    if not (-180.0 <= lon <= 180.0):
        raise typer.BadParameter("longitude must be between -180 and 180")


def _select_location_interactive(current: Location) -> Location:
    mode = _prompt_choice(
        "Location mode",
        ("keep", "auto", "search", "manual"),
        "keep",
    )

    if mode == "keep":
        return current

    if mode == "auto":
        try:
            location = detect_location_from_ip()
            console.print(
                f"[green]Detected location:[/green] {location.city}, {location.country}"
            )
            return location
        except Exception as exc:  # noqa: BLE001
            raise typer.BadParameter(f"Failed to auto-detect location: {exc}") from exc

    if mode == "search":
        query = typer.prompt("Search query")
        results = search_locations(query, limit=5)
        if not results:
            raise typer.BadParameter("No results from geocoding API")

        console.print("Select location:")
        for index, loc in enumerate(results, start=1):
            label = loc.addressLabel or f"{loc.city}, {loc.country}"
            console.print(f"  {index}. {label}")

        selected_index = typer.prompt("Result number", default="1")
        try:
            index = int(selected_index)
        except ValueError as exc:
            raise typer.BadParameter("Result number must be an integer") from exc

        if index < 1 or index > len(results):
            raise typer.BadParameter("Result number out of range")
        return results[index - 1]

    city = typer.prompt("City", default=current.city)
    country = typer.prompt("Country", default=current.country)
    country_code = typer.prompt("Country code", default=current.countryCode).upper()
    lat = float(typer.prompt("Latitude", default=str(current.lat)))
    lon = float(typer.prompt("Longitude", default=str(current.lon)))

    address_label_default = current.addressLabel or ""
    address_label = typer.prompt("Address label (optional)", default=address_label_default)

    diyanet_default = current.diyanetIlceId or ""
    diyanet_ilce_id = typer.prompt(
        "Diyanet ilce id (optional)",
        default=diyanet_default,
    )

    return Location(
        city=city,
        country=country,
        countryCode=country_code,
        lat=lat,
        lon=lon,
        addressLabel=address_label or None,
        diyanetIlceId=diyanet_ilce_id or None,
    )


def _print_config(config: Config) -> None:
    payload = config.to_dict()
    console.print_json(json.dumps(payload, ensure_ascii=False, indent=2))
    console.print(f"[dim]Config path:[/dim] {CONFIG_PATH}")


def _show_today() -> None:
    config = load_config()

    try:
        bundle = fetch_prayer_bundle(config.location, config.prayer_source)
    except PrayerApiError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Unexpected error:[/red] {exc}")
        raise typer.Exit(code=1)

    info = get_current_prayer_info(
        bundle.times,
        bundle.tomorrow_fajr,
        bundle.time_zone,
    )

    render_today(
        console=console,
        location=config.location,
        prayer_times=bundle.times,
        info=info,
        time_format=config.time_format,
        time_zone=bundle.time_zone,
        source=bundle.resolved_source,
    )


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Show today's prayer times."""
    _ = version
    if ctx.invoked_subcommand is None:
        _show_today()


@app.command("next")
def next_command(
    once: bool = typer.Option(False, "--once", help="Show next prayer once and exit."),
) -> None:
    """Show next prayer and a live countdown."""
    config = load_config()

    try:
        bundle = fetch_prayer_bundle(config.location, config.prayer_source)
    except PrayerApiError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    def _current_panel() -> Any:
        info = get_current_prayer_info(
            bundle.times,
            bundle.tomorrow_fajr,
            bundle.time_zone,
        )
        return build_next_panel(
            location=config.location,
            info=info,
            time_format=config.time_format,
            source=bundle.resolved_source,
        )

    if once:
        console.print(_current_panel())
        return

    try:
        with Live(_current_panel(), console=console, refresh_per_second=4) as live:
            while True:
                info = get_current_prayer_info(
                    bundle.times,
                    bundle.tomorrow_fajr,
                    bundle.time_zone,
                )
                live.update(
                    build_next_panel(
                        location=config.location,
                        info=info,
                        time_format=config.time_format,
                        source=bundle.resolved_source,
                    )
                )

                if info.time_until_next_ms <= 1000:
                    try:
                        bundle = fetch_prayer_bundle(config.location, config.prayer_source)
                    except PrayerApiError:
                        pass
                time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


@app.command("config")
def config_command(
    show: bool = typer.Option(False, "--show", help="Print current configuration."),
    auto_location: bool = typer.Option(
        False,
        "--auto-location",
        help="Detect location from IP and map to nearest built-in city.",
    ),
    search: Optional[str] = typer.Option(
        None,
        "--search",
        help="Search a location using OpenStreetMap Nominatim.",
    ),
    search_index: int = typer.Option(
        1,
        "--search-index",
        min=1,
        help="Result index used with --search (1-based).",
    ),
    city: Optional[str] = typer.Option(None, "--city"),
    country: Optional[str] = typer.Option(None, "--country"),
    country_code: Optional[str] = typer.Option(None, "--country-code"),
    lat: Optional[float] = typer.Option(None, "--lat"),
    lon: Optional[float] = typer.Option(None, "--lon"),
    address_label: Optional[str] = typer.Option(None, "--address-label"),
    diyanet_ilce_id: Optional[str] = typer.Option(None, "--diyanet-ilce-id"),
    method: Optional[str] = typer.Option(
        None,
        "--method",
        help="Calculation source preference: diyanet or mwl.",
    ),
    time_format: Optional[str] = typer.Option(
        None,
        "--time-format",
        help="Display format: 12h or 24h.",
    ),
) -> None:
    """Set location, calculation method, and time format."""
    config = load_config()

    manual_location_flag = any(
        value is not None for value in (city, country, country_code, lat, lon)
    )
    has_update_flags = any(
        [
            auto_location,
            search is not None,
            manual_location_flag,
            method is not None,
            time_format is not None,
            address_label is not None,
            diyanet_ilce_id is not None,
        ]
    )

    if show and not has_update_flags:
        _print_config(config)
        return

    if not has_update_flags:
        console.print("[bold]Interactive configuration[/bold]")
        config.location = _select_location_interactive(config.location)

        method_value = _prompt_choice(
            "Calculation method",
            ("diyanet", "mwl"),
            config.prayer_source,
        )
        config.prayer_source = _validate_source(method_value)

        format_value = _prompt_choice(
            "Time format",
            ("12h", "24h"),
            config.time_format,
        )
        config.time_format = _validate_time_format(format_value)

        save_config(config)
        console.print("[green]Configuration saved.[/green]")
        _print_config(config)
        return

    if auto_location:
        try:
            config.location = detect_location_from_ip()
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to detect location:[/red] {exc}")
            raise typer.Exit(code=1)

    if search is not None:
        results = search_locations(search, limit=5)
        if not results:
            console.print("[red]No search results.[/red]")
            raise typer.Exit(code=1)
        if search_index < 1 or search_index > len(results):
            console.print(
                f"[red]search-index out of range. Pick 1..{len(results)}[/red]"
            )
            raise typer.Exit(code=1)
        config.location = results[search_index - 1]

    if manual_location_flag:
        required = [city, country, country_code, lat, lon]
        if any(value is None for value in required):
            console.print(
                "[red]Manual location requires --city --country --country-code --lat --lon.[/red]"
            )
            raise typer.Exit(code=1)

        assert lat is not None
        assert lon is not None
        _validate_coordinates(lat, lon)

        config.location = Location(
            city=city or "",
            country=country or "",
            countryCode=(country_code or "").upper(),
            lat=float(lat),
            lon=float(lon),
            addressLabel=address_label,
            diyanetIlceId=diyanet_ilce_id,
        )

    if not manual_location_flag and address_label is not None:
        config.location.addressLabel = address_label

    if not manual_location_flag and diyanet_ilce_id is not None:
        config.location.diyanetIlceId = diyanet_ilce_id

    if method is not None:
        config.prayer_source = _validate_source(method)

    if time_format is not None:
        config.time_format = _validate_time_format(time_format)

    save_config(config)
    console.print("[green]Configuration saved.[/green]")
    _print_config(config)


@app.command("notify")
def notify_command() -> None:
    """Daemon mode: send a system notification at each prayer time."""
    config = load_config()
    try:
        run_notify_daemon(
            console=console,
            location=config.location,
            source=config.prayer_source,
            time_format=config.time_format,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Notification daemon stopped.[/dim]")


if __name__ == "__main__":
    app()
