"""Create separate 1600 x 650 video PNGs without altering standard plots."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile

OUTPUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("walkthrough_charts", OUTPUT / "build_charts.py")
charts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(charts)


def video_canvas():
    fig, ax = charts.plt.subplots(figsize=(16, 6.5), dpi=100)
    fig.subplots_adjust(left=.115, right=.975, bottom=.21, top=.94)
    ax.grid(axis="y", color="#DCE3E9", linewidth=1.1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=6, width=1.25, pad=9)
    return fig, ax


def video_save(fig, name):
    ax = fig.axes[0]
    if name == "02_reserve_tonnes":
        ax.set_ylim(0, 285)
    if name == "05_pooled_rmse":
        ax.set_ylabel("Pooled RMSE (°C)\nGenerated target", linespacing=1.15)
        ax.set_ylim(0, .05)
    leg = ax.get_legend()
    if leg is not None:
        leg.set_frame_on(True)
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_edgecolor("none")
        leg.get_frame().set_alpha(1)
    for suffix in ("png", "svg"):
        fig.savefig(charts.HERE / f"{name}.{suffix}", dpi=100)
    charts.plt.close(fig)


def main():
    standard_paths = sorted(OUTPUT.glob("0[1-5]_*.png"))
    standard_hashes = {str(p): charts.digest(p) for p in standard_paths if not p.stem.endswith("_video")}
    source_metadata_hash = charts.digest(OUTPUT / "sources.json")
    charts.canvas = video_canvas
    charts.save = video_save
    with tempfile.TemporaryDirectory(prefix="apcom_video_charts_") as stage:
        charts.HERE = Path(stage)
        charts.main()
        metadata = json.loads((charts.HERE / "sources.json").read_text(encoding="utf-8"))
        metadata["dimensions_px"] = [1600, 650]
        metadata["purpose"] = "Shorter teaching plots for a 1080p video with a title and caption area"
        for chart in metadata["charts"]:
            original = charts.HERE / chart["file"]
            target = OUTPUT / f"{original.stem}_video.png"
            shutil.copyfile(original, target)
            assert struct.unpack(">II", target.read_bytes()[16:24]) == (1600, 650)
            chart["file"] = target.name
            chart["png_sha256"] = charts.digest(target)
        metadata["validation"]["standard_chart_hashes_unchanged"] = all(charts.digest(Path(p)) == h for p, h in standard_hashes.items())
        metadata["validation"]["standard_source_metadata_unchanged"] = charts.digest(OUTPUT / "sources.json") == source_metadata_hash
        assert metadata["validation"]["standard_chart_hashes_unchanged"]
        assert metadata["validation"]["standard_source_metadata_unchanged"]
        (OUTPUT / "sources_video.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Created five separate 1600 x 650 video PNGs; all standard charts unchanged.")


if __name__ == "__main__":
    main()
