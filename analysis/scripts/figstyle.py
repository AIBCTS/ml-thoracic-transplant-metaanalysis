"""
figstyle.py - one switch for the decimal mark used in every generated figure and table.

    from figstyle import DEC, dec, fmt, axis_formatter, smart_axis_formatter

Reads config.yaml -> figures.decimal_mark ("middot" | "period"); the environment variable
FIG_DECIMAL_MARK overrides it. Added 2026-09-04 so the package can be re-rendered for a
journal that uses period decimals (NEJM AI) by changing one line.
"""
import os, re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

def _read_mark():
    v = os.environ.get("FIG_DECIMAL_MARK")
    if not v:
        try:
            import yaml
            v = (yaml.safe_load(open(_ROOT / "config.yaml")) or {}).get("figures", {}).get("decimal_mark")
        except Exception:
            v = None
    v = (v or "middot").strip().lower()
    if v not in ("middot", "period"):
        raise SystemExit(f"figures.decimal_mark must be 'middot' or 'period', got {v!r}")
    return v

DECIMAL_MARK = _read_mark()
DEC = "\u00b7" if DECIMAL_MARK == "middot" else "."

def dec(s):
    """Replace the decimal point between digits in a string with the configured mark."""
    return re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + DEC + m.group(2), str(s))

def fmt(x, nd=3):
    """Fixed-decimal number with the configured mark: fmt(0.6949, 3) -> '0·695' or '0.695'."""
    return dec(f"{x:.{nd}f}")

def axis_formatter(spec="{:.2f}"):
    """matplotlib FuncFormatter applying `spec` then the configured mark."""
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda v, _p: dec(spec.format(v)))

def smart_axis_formatter():
    """1 or 2 decimals as needed (0·7, 0·75), configured mark."""
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda v, _p: dec(f"{v:.2f}" if abs(v - round(v, 1)) > 1e-9 else f"{v:.1f}"))

def g_axis_formatter():
    """General format (%g) with the configured mark - for 0.5, 0.6 ... 1 axes."""
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda v, _p: dec(f"{v:g}"))
