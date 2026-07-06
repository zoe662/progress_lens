import os
import shlex
import sys
from pathlib import Path


CLICKUP_ENV_KEYS = ("CLICKUP_TOKEN", "CLICKUP_LIST_ID")
START_MARKER = "# >>> progress-updater clickup env >>>"
END_MARKER = "# <<< progress-updater clickup env <<<"


def _activation_candidates() -> list[Path]:
    candidates = []

    virtual_env = os.getenv("VIRTUAL_ENV")
    if virtual_env:
        candidates.append(Path(virtual_env) / "bin" / "activate")

    candidates.append(Path(sys.prefix) / "bin" / "activate")
    candidates.append(Path(__file__).resolve().parents[3] / ".venv" / "bin" / "activate")

    return list(dict.fromkeys(candidates))


def _read_clickup_block(path: Path) -> list[str]:
    if not path.exists():
        return []

    in_block = False
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == START_MARKER:
            in_block = True
            continue
        if line == END_MARKER:
            break
        if in_block:
            lines.append(line)

    return lines


def _parse_export(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped.startswith("export "):
        return None

    try:
        parts = shlex.split(stripped)
    except ValueError:
        return None

    for part in parts[1:]:
        key, sep, value = part.partition("=")
        if sep and key in CLICKUP_ENV_KEYS:
            return key, value

    return None


def read_clickup_env_from_venv(candidates: list[Path] | None = None) -> dict[str, str]:
    values = {}

    for activate_path in candidates or _activation_candidates():
        for line in _read_clickup_block(activate_path):
            parsed = _parse_export(line)
            if not parsed:
                continue
            key, value = parsed
            values.setdefault(key, value)
        if all(key in values for key in CLICKUP_ENV_KEYS):
            break

    return values


def load_clickup_env_from_venv() -> None:
    missing = {key for key in CLICKUP_ENV_KEYS if not os.getenv(key)}
    if not missing:
        return

    values = read_clickup_env_from_venv()
    for key in list(missing):
        value = values.get(key)
        if value:
            os.environ[key] = value
