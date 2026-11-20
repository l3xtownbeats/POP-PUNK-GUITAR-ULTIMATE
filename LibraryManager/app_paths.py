"""Runtime paths for source, portable and installed Manager builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path


APP_FOLDER_NAME = "POP PUNK GUITAR Library Manager"


def resolve_runtime_paths(
    module_file: str | Path,
    *,
    executable: str | Path | None = None,
    frozen: bool | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[Path, Path, bool]:
    """Return (bundle_dir, writable_data_dir, portable_mode).

    Portable builds keep UserData beside the executable. Installed builds keep
    mutable data under LocalAppData, never Program Files or PyInstaller _MEIPASS.
    Source checkouts keep their historic in-tree reports/staging layout.
    """
    env = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if is_frozen:
        exe = Path(executable or sys.executable).expanduser().resolve()
        bundle = exe.parent
        portable = (bundle / "portable.mode").is_file()
        if portable:
            data = bundle / "UserData"
        else:
            local = env.get("LOCALAPPDATA")
            base = Path(local).expanduser() if local else Path.home() / "AppData" / "Local"
            data = base / APP_FOLDER_NAME
        return bundle, data.resolve(), portable

    module_dir = Path(module_file).expanduser().resolve().parent
    return module_dir, module_dir, False


def resource_file(name: str, *, module_file: str | Path,
                  bundle_dir: str | Path | None = None) -> Path:
    """Resolve read-only packaged resources without writing into the bundle."""
    module_dir = Path(module_file).resolve().parent
    roots = []
    if getattr(sys, "_MEIPASS", None):
        roots.append(Path(sys._MEIPASS))
    if bundle_dir is not None:
        roots.append(Path(bundle_dir))
    roots.append(module_dir)
    for root in roots:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return roots[0] / name if roots else module_dir / name


def runtime_staging_root(module_file: str | Path) -> Path:
    """Return the same writable staging root used by the GUI in every build mode."""
    _bundle, data_dir, _portable = resolve_runtime_paths(module_file)
    return (data_dir / "staging").resolve()
