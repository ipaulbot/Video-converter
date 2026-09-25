"""Accessibility: Ease of Access feature flags and the cursor/text settings that affect observation UIs."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import Section, first_dict, kv_groups

FEATURES = ("StickyKeys", "ToggleKeys", "FilterKeys", "MouseKeys", "SoundSentry", "HighContrast",
            "Keyboard Response", "TimeOut")
SWITCHES = ("ShowSounds", "Keyboard Preference", "Blind Access")

SCRIPT = r"""
$root = 'HKCU:\Control Panel\Accessibility'
$o = [ordered]@{}
foreach ($k in 'StickyKeys','ToggleKeys','FilterKeys','MouseKeys','SoundSentry','HighContrast','Keyboard Response','TimeOut') {
  $o[$k] = (Get-ItemProperty "$root\$k" -ErrorAction SilentlyContinue).Flags
}
foreach ($k in 'ShowSounds','Keyboard Preference','Blind Access') {
  $o[$k] = (Get-ItemProperty "$root\$k" -ErrorAction SilentlyContinue).On
}
$desk = Get-ItemProperty 'HKCU:\Control Panel\Desktop' -ErrorAction SilentlyContinue
$o.CursorBlinkRate = $desk.CursorBlinkRate
$o.CaretWidth = $desk.CaretWidth
$o.MouseScheme = (Get-ItemProperty 'HKCU:\Control Panel\Cursors' -ErrorAction SilentlyContinue).'(default)'
$o.TextScaleFactor = (Get-ItemProperty 'HKCU:\Software\Microsoft\Accessibility' -ErrorAction SilentlyContinue).TextScaleFactor
$o.HighContrastScheme = (Get-ItemProperty "$root\HighContrast" -ErrorAction SilentlyContinue).'High Contrast Scheme'
[pscustomobject]$o
"""


def _title(name: str) -> str:
    return {"StickyKeys": "Sticky Keys", "ToggleKeys": "Toggle Keys", "FilterKeys": "Filter Keys",
            "MouseKeys": "Mouse Keys", "SoundSentry": "Sound Sentry", "HighContrast": "High Contrast",
            "TimeOut": "Accessibility Time-out", "ShowSounds": "Show Sounds"}.get(name, name)


def build(raw: dict) -> dict:
    raw = raw or {}
    settings = {
        "Cursor Blink Rate": f"{raw['CursorBlinkRate']} ms" if raw.get("CursorBlinkRate") not in (None, "") else "",
        "Caret Width": f"{raw['CaretWidth']} px" if raw.get("CaretWidth") not in (None, "") else "",
        "Mouse Pointer Scheme": raw.get("MouseScheme") or "Windows Default",
        "Text Scale": f"{raw['TextScaleFactor']} %" if raw.get("TextScaleFactor") not in (None, "") else "100 %",
        "High Contrast Scheme": raw.get("HighContrastScheme", ""),
    }
    for name in SWITCHES:
        value = raw.get(name)
        settings[_title(name)] = yes_no(decode.to_int(value)) if value not in (None, "") else ""
    groups = [{"title": "Settings", "rows": settings}]
    for name in FEATURES:
        if raw.get(name) in (None, ""):
            continue
        groups.append({"title": _title(name), "rows": decode.accessibility_flags(raw.get(name))})
    return {"groups": groups}


def collect(ctx):
    return build(first_dict(ctx.query("settings", SCRIPT)))


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="accessibility", title="Accessibility", group="Software", collect=collect, render=render)
