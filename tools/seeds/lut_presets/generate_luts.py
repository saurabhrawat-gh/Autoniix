"""Generate the 7 built-in finishing LUTs as Resolve-compatible .cube files
(AE-294, Phase 1A).

These are self-authored parametric grades (open, no third-party licence) so the
finishing pipeline always has a real ``lut3d`` file to apply. Run as a script to
write all 7 .cube files into this directory and (optionally) upload them to MinIO
at ``luts/{key}.cube``.

    python -m scripts.seeds.lut_presets.generate_luts            # write files
    python -m scripts.seeds.lut_presets.generate_luts --upload   # + push to MinIO

The same ``write_cube`` helper is imported by the finishing activity as a
self-heal fallback when a preset's .cube is missing from MinIO.
"""

from __future__ import annotations

import argparse
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
LUT_SIZE = 17


def _clamp(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


# Per-preset grade parameters.
#   temp        : warm (+) / cool (-) shift
#   contrast    : >1 punchier, <1 flatter
#   saturation  : 1.0 neutral, <1 desaturated, >1 vivid
#   lift        : (r,g,b) added to shadows
#   gain        : (r,g,b) multiplicative highlights tint
_PRESETS: dict[str, dict] = {
    "cinematic": {
        "temp": 0.04,
        "contrast": 1.12,
        "saturation": 1.05,
        "lift": (0.01, 0.0, 0.02),
        "gain": (1.06, 1.0, 0.94),
    },
    "clean_bright": {
        "temp": 0.0,
        "contrast": 1.08,
        "saturation": 1.12,
        "lift": (0.0, 0.0, 0.0),
        "gain": (1.04, 1.04, 1.05),
    },
    "warm_gold": {
        "temp": 0.08,
        "contrast": 1.05,
        "saturation": 1.04,
        "lift": (0.02, 0.01, 0.0),
        "gain": (1.08, 1.02, 0.9),
    },
    "cool_blue": {
        "temp": -0.07,
        "contrast": 1.15,
        "saturation": 0.9,
        "lift": (0.0, 0.0, 0.02),
        "gain": (0.95, 1.0, 1.08),
    },
    "vintage": {
        "temp": 0.03,
        "contrast": 0.92,
        "saturation": 0.85,
        "lift": (0.05, 0.04, 0.03),
        "gain": (1.02, 0.99, 0.95),
    },
    "documentary": {"temp": 0.0, "contrast": 1.0, "saturation": 0.82, "lift": (0.0, 0.0, 0.0), "gain": (1.0, 1.0, 1.0)},
    "neon_dark": {
        "temp": -0.03,
        "contrast": 1.25,
        "saturation": 1.2,
        "lift": (0.0, 0.0, 0.01),
        "gain": (1.05, 0.97, 1.1),
    },
}


def _grade(r: float, g: float, b: float, p: dict) -> tuple[float, float, float]:
    # Temperature: push red up / blue down for warm, opposite for cool.
    r += p["temp"]
    b -= p["temp"]

    # Contrast around mid-grey.
    c = p["contrast"]
    r = (r - 0.5) * c + 0.5
    g = (g - 0.5) * c + 0.5
    b = (b - 0.5) * c + 0.5

    # Saturation (mix toward Rec.709 luma).
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    s = p["saturation"]
    r = luma + (r - luma) * s
    g = luma + (g - luma) * s
    b = luma + (b - luma) * s

    # Lift (shadows) + gain (highlights tint).
    lr, lg, lb = p["lift"]
    gr, gg, gb = p["gain"]
    r = r * gr + lr * (1.0 - r)
    g = g * gg + lg * (1.0 - g)
    b = b * gb + lb * (1.0 - b)

    return _clamp(r), _clamp(g), _clamp(b)


def write_cube(preset_key: str, dest_path: str, size: int = LUT_SIZE) -> str:
    """Write a .cube 3D LUT for *preset_key* to *dest_path*. Returns the path."""
    params = _PRESETS.get(preset_key, _PRESETS["documentary"])
    lines = [
        f'TITLE "autoniix-{preset_key}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    denom = size - 1
    # .cube ordering: red index varies fastest.
    for bi in range(size):
        for gi in range(size):
            for ri in range(size):
                r, g, b = _grade(ri / denom, gi / denom, bi / denom, params)
                lines.append(f"{r:.6f} {g:.6f} {b:.6f}")
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(dest_path).write_text("\n".join(lines) + "\n")
    return dest_path


def write_all(out_dir: Path = OUT_DIR) -> list[str]:
    written = []
    for key in _PRESETS:
        path = out_dir / f"{key}.cube"
        write_cube(key, str(path))
        written.append(str(path))
    return written


def _upload_all(out_dir: Path = OUT_DIR) -> None:
    import asyncio

    import providers.boot  # noqa: F401 - registers storage providers
    from providers.registry import ProviderRegistry
    from providers.storage.base import StorageUpload

    async def _go() -> None:
        storage = ProviderRegistry.get("storage")
        for key in _PRESETS:
            data = (out_dir / f"{key}.cube").read_bytes()
            await storage.upload(StorageUpload(key=f"luts/{key}.cube", data=data, content_type="text/plain"))
            print(f"  uploaded luts/{key}.cube ({len(data)} bytes)")

    asyncio.run(_go())


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate finishing LUT .cube files")
    ap.add_argument("--upload", action="store_true", help="upload to MinIO after writing")
    args = ap.parse_args()

    paths = write_all()
    print(f"Wrote {len(paths)} LUTs to {OUT_DIR}")
    for p in paths:
        print(f"  {p}")
    if args.upload:
        _upload_all()


if __name__ == "__main__":
    main()
