from pathlib import Path
import tempfile
import configparser
import json
import lz4.block
from typing import List, Dict

_MAGIC = b"mozLz40\0"


def compress(src, dest) -> None:
    data = Path(src).read_bytes()
    output = _MAGIC + lz4.block.compress(data)
    dest_path = Path(dest)
    tmp = dest_path.parent / (dest_path.name + ".tmp")
    try:
        tmp.write_bytes(output)
        tmp.replace(dest_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def decompress(src, dest) -> None:
    data = Path(src).read_bytes()
    if len(data) < len(_MAGIC) or data[:len(_MAGIC)] != _MAGIC:
        raise ValueError(f"Not a valid mozLz4 file: {src}")
    decompressed = lz4.block.decompress(data[len(_MAGIC):])
    dest_path = Path(dest)
    tmp = dest_path.parent / (dest_path.name + ".tmp")
    try:
        tmp.write_bytes(decompressed)
        tmp.replace(dest_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def get_firefox_path() -> Path:
    """Return the Path to the user's Firefox directory (~/.mozilla/firefox)."""
    return Path.home() / ".mozilla" / "firefox"


def list_profiles() -> List[Dict[str, str]]:
    """Parse `profiles.ini` and return a list of profiles as dicts with `name` and `path`.

    The returned `path` is absolute. Returns empty list if profiles.ini does not exist.
    """
    firefox_path = get_firefox_path()
    ini_path = firefox_path / "profiles.ini"
    if not ini_path.exists():
        return []
    config = configparser.ConfigParser()
    config.read(ini_path)
    profiles: List[Dict[str, str]] = []
    for section in config.sections():
        if not config.has_option(section, "Path"):
            continue
        raw_path = config.get(section, "Path")
        is_relative = config.get(section, "IsRelative", fallback="1")
        if is_relative in ("1", "true", "True"):
            profile_path = firefox_path / raw_path
        else:
            profile_path = Path(raw_path)
        profiles.append({"name": config.get(section, "Name", fallback=section), "path": str(profile_path)})
    return profiles


def get_profile_path_by_index(index: int) -> Path:
    """Return the Path for profile at 0-based index from `list_profiles()`.

    Raises IndexError if not found.
    """
    profiles = list_profiles()
    if index < 0 or index >= len(profiles):
        raise IndexError("profile index out of range")
    return Path(profiles[index]["path"])


def get_available_themes(profile_path: Path) -> List[Dict]:
    """Return the list of theme addon objects from `extensions.json` for the given profile.

    Returns empty list if extensions.json does not exist.
    Raises ValueError on malformed JSON.
    """
    extensions_file = Path(profile_path) / "extensions.json"
    if not extensions_file.exists():
        return []
    try:
        data = json.loads(extensions_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse extensions.json: {exc}") from exc
    return [addon for addon in data.get("addons", []) if addon.get("type") == "theme"]


def set_active_theme_in_prefs(profile_path: Path, theme_id: str) -> None:
    """Set `extensions.activeThemeID` in `prefs.js` to `theme_id`.

    If the preference line does not exist, append it. Writes atomically.
    """
    prefs_js_path = Path(profile_path) / "prefs.js"
    if not prefs_js_path.exists():
        raise FileNotFoundError(f"prefs.js not found: {prefs_js_path}")
    lines = prefs_js_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    found = False
    for line in lines:
        if 'user_pref("extensions.activeThemeID", ' in line:
            new_lines.append(f'user_pref("extensions.activeThemeID", "{theme_id}");\n')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'user_pref("extensions.activeThemeID", "{theme_id}");\n')
    content = "".join(new_lines)
    tmp = prefs_js_path.parent / (prefs_js_path.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(prefs_js_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def set_active_theme_in_extensions(profile_path: Path, theme_id: str) -> None:
    """Update `extensions.json` to enable the chosen theme and disable others.

    Writes atomically.
    """
    extension_json_path = Path(profile_path) / "extensions.json"
    if not extension_json_path.exists():
        raise FileNotFoundError(f"extensions.json not found: {extension_json_path}")
    data = json.loads(extension_json_path.read_text(encoding="utf-8"))
    for addon in data.get("addons", []):
        if addon.get("type") == "theme":
            active = addon.get("id") == theme_id
            addon["userDisabled"] = not active
            addon["active"] = active
    content = json.dumps(data)
    tmp = extension_json_path.parent / (extension_json_path.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(extension_json_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def set_active_theme_in_addon_startup(profile_path: Path, theme_id: str) -> None:
    """Update `addonStartup.json.lz4` enabling only `theme_id`.

    Decompresses to a unique temp file, modifies, then recompresses atomically.
    """
    lz4_path = Path(profile_path) / "addonStartup.json.lz4"
    if not lz4_path.exists():
        raise FileNotFoundError(f"addonStartup.json.lz4 not found: {lz4_path}")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_fh:
        tmp_path = Path(tmp_fh.name)
    try:
        decompress(lz4_path, tmp_path)
        data = json.loads(tmp_path.read_text(encoding="utf-8"))
        for aid, addon in data.get("app-profile", {}).get("addons", {}).items():
            if addon.get("type") == "theme":
                addon["enabled"] = (aid == theme_id)
        tmp_path.write_text(json.dumps(data), encoding="utf-8")
        compress(tmp_path, lz4_path)
    finally:
        tmp_path.unlink(missing_ok=True)


__all__ = [
    "decompress",
    "compress",
    "get_firefox_path",
    "list_profiles",
    "get_profile_path_by_index",
    "get_available_themes",
    "set_active_theme_in_prefs",
    "set_active_theme_in_extensions",
    "set_active_theme_in_addon_startup",
]
