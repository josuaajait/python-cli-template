"""Optional per-user defaults from a TOML file.

    color = false             # same as --no-color
    quiet = true              # same as --quiet
    log_dir = "~/cli-logs"    # same as --log-dir; relative paths start at this file's folder
    archive = false           # same as --no-archive

Command-line flags and environment variables win over the file. The output
format is deliberately not configurable: redirected stdout must stay JSON.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tomllib


class ConfigError(Exception):
    """The configuration file exists but cannot be used."""


@dataclass(frozen=True)
class Settings:
    path: Path
    loaded: bool = False
    color: bool | None = None
    quiet: bool | None = None
    log_dir: Path | None = None
    archive: bool | None = None


_KNOWN = ('color', 'quiet', 'log_dir', 'archive')


def config_path(override: str | None = None, *, app_id: str, env: str) -> tuple[Path, bool]:
    """The config file to read and whether the user named it explicitly."""
    chosen = override or os.environ.get(env)
    if chosen:
        return Path(chosen).expanduser().absolute(), True
    if os.name == 'nt':
        base = Path(os.environ['APPDATA']) if 'APPDATA' in os.environ else Path.home() / 'AppData/Roaming'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ['XDG_CONFIG_HOME']) if 'XDG_CONFIG_HOME' in os.environ else Path.home() / '.config'
    return base / app_id / 'config.toml', False


def load_settings(path: Path, *, explicit: bool = False) -> Settings:
    """Read and validate `path`; a missing default file means no settings."""
    try:
        with path.open('rb') as stream:
            data = tomllib.load(stream)
    except FileNotFoundError:
        if explicit:
            raise ConfigError(f'Config file not found: {path}') from None
        return Settings(path)
    except IsADirectoryError:
        raise ConfigError(f'Config path is a directory: {path}') from None
    except PermissionError as error:
        raise ConfigError(f'Cannot read config file {path}: {error.strerror}') from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f'Invalid TOML in {path}: {error}') from None

    unknown = sorted(set(data) - set(_KNOWN))
    if unknown:
        raise ConfigError(f'Unknown setting "{unknown[0]}" in {path}; expected one of: {", ".join(_KNOWN)}.')
    log_dir = None
    if 'log_dir' in data:
        if not isinstance(data['log_dir'], str) or not data['log_dir'].strip():
            raise ConfigError(f'Setting "log_dir" in {path} must be a non-empty string.')
        log_dir = (path.parent / Path(data['log_dir']).expanduser()).absolute()
    return Settings(path, True, color=_flag(data, 'color', path), quiet=_flag(data, 'quiet', path),
                    log_dir=log_dir, archive=_flag(data, 'archive', path))


def _flag(data: dict[str, object], key: str, path: Path) -> bool | None:
    value = data.get(key)
    if value is not None and not isinstance(value, bool):
        raise ConfigError(f'Setting "{key}" in {path} must be true or false.')
    return value
