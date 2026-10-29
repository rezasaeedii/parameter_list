"""Finding a browser and opening it **without any network access**.

The company machines have no internet connection, so this module exists to make
one promise explicit and testable:

    nothing in this tool ever contacts a server other than 127.0.0.1

Two things are needed for that:

1. The pages themselves must not reference anything outside the machine.  They
   do not: every script, style and font in ``web/`` sits next to the page.
2. A Chromium based browser started for us must not do its own background
   networking (update checks, safe-browsing lists, sync, telemetry).  That is
   what :data:`OFFLINE_FLAGS` switches off.

If no Chromium based browser is found, the caller falls back to the machine's
default browser, which opens a plain ``http://127.0.0.1`` page - still local.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

#: Names looked up on the PATH, on any operating system.
BROWSER_COMMANDS = [
    "msedge", "microsoft-edge", "microsoft-edge-stable",
    "chrome", "google-chrome", "google-chrome-stable",
    "chromium", "chromium-browser", "brave", "brave-browser",
]

#: Well known installation paths, checked when the PATH lookup fails.
BROWSER_PATHS = {
    "win32": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    # A macOS program is a bundle folder whose name ends in ".app".  These three
    # once read ".pl_app" - a rename of the tool's own "app" folder that swept
    # through them too - so a Mac never found one of them, and the editor always
    # fell back to a plain tab of the default browser instead of its own window.
    "darwin": [
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "linux": [
        "/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium",
        "/usr/bin/chromium-browser", "/snap/bin/chromium",
    ],
}

#: Every switch that stops a Chromium based browser from talking to the network
#: on its own.  They are all plain command line switches, supported by Edge,
#: Chrome, Chromium and Brave.
OFFLINE_FLAGS: List[str] = [
    "--disable-background-networking",   # the umbrella switch
    "--disable-component-update",        # no component / codec downloads
    "--disable-sync",                    # no account sync
    "--disable-domain-reliability",      # no reliability beacons
    "--disable-breakpad",                # no crash upload
    "--safebrowsing-disable-auto-update",
    "--metrics-recording-only",          # collect nothing, send nothing
    "--disable-features=Translate,OptimizationHints,MediaRouter,"
    "InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-extensions",
]


def find_browser() -> Optional[str]:
    """Path of a Chromium based browser, or ``None`` when there is none.

    ``PL_CODEGEN_BROWSER`` overrides the search, for a portable installation
    that is not on the PATH.
    """
    override = os.environ.get("PL_CODEGEN_BROWSER")
    if override and Path(override).is_file():
        return override

    for command in BROWSER_COMMANDS:
        found = shutil.which(command)
        if found:
            return found

    platform = "win32" if sys.platform.startswith("win") else \
               "darwin" if sys.platform == "darwin" else "linux"
    for candidate in BROWSER_PATHS.get(platform, []):
        if Path(candidate).is_file():
            return candidate
    return None


def app_window_command(browser: str, url: str, profile_directory: str) -> List[str]:
    """Command that opens *url* as a borderless application window.

    ``--app=`` gives a window with no address bar and no tab strip, so the
    editor looks like a normal desktop program instead of a web page.  The
    throw-away profile keeps the user's own browser session untouched.
    """
    return [
        browser,
        f"--app={url}",
        f"--user-data-dir={profile_directory}",
        "--window-size=1500,950",
        *OFFLINE_FLAGS,
    ]
