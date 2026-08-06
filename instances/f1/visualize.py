"""
F1 instance — reporting/visualization.
Mechanical extraction of the matplotlib section from the original
governance_engine.py. Instance-specific (track shape, annotations),
not part of the core.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from instances.f1.run import ver, corner_i, open_i, CHANNELS

OUT = os.path.dirname(__file__)
INK = "#1a1a2e"
CH_ORDER = ["Voice", "Presence", "Vision", "Sound", "Touch"]   # top -> bottom
CH_COLOR = {"Voice": "#6c5ce7", "Presence": "#00b4d8",
            "Vision": "#e84393", "Sound": "#fdcb6e", "Touch": "#00d084"}


def make_figures():
    # ---- Figure 1: the lap, coloured by cognitive load --------------------
    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(ver["X"], ver["Y"], c=ver["load"], cmap="inferno",
                     s=14, vmin=0, vmax=1)
    ANN = {
        corner_i: dict(t="THE CORNER\nattention ~0 · silence + one reflex cue",
                       c="#00b86b", xy=(55, -60)),
        open_i:   dict(t="THE STRAIGHT\nattention open · channels open up",
                       c="#0096c7", xy=(-70, 34)),
    }
    for i, a in ANN.items():
        ax.scatter(ver["X"].iloc[i], ver["Y"].iloc[i], s=340, marker="*",
                   edgecolor="white", facecolor=a["c"], zorder=5, linewidth=1.6)
        ax.annotate(a["t"], (ver["X"].iloc[i], ver["Y"].iloc[i]),
                    textcoords="offset points", xytext=a["xy"], ha="center",
                    fontsize=9, fontweight="bold", color=INK,
                    bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=a["c"], lw=1.5),
                    arrowprops=dict(arrowstyle="-", color=a["c"], lw=1.3))
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Abu Dhabi 2021 · final lap, coloured by the driver's cognitive load",
                 fontsize=12, fontweight="bold", color=INK, pad=14)
    cb = plt.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("cognitive load  (low -> high)", fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig1_track_load.png"), dpi=160, bbox_inches="tight")
    plt.close()

    # ---- Figure 2: what the system does, across the lap -------------------
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True,
                                 gridspec_kw=dict(height_ratios=[1, 1.3], hspace=0.12))
    d = ver["Distance"].to_numpy()

    a1.fill_between(d, ver["load"], color="#e84393", alpha=0.18)
    a1.plot(d, ver["load"], color="#e84393", lw=1.6)
    a1.set_ylabel("cognitive\nload", fontsize=9); a1.set_ylim(0, 1.05)
    a1.set_title("What reaches the driver, moment to moment  (green = channel speaking)",
                 fontsize=12, fontweight="bold", color=INK, loc="left", pad=10)
    for sp in ["top", "right"]:
        a1.spines[sp].set_visible(False)

    for row, ch in enumerate(CH_ORDER):
        on = ver[ch].to_numpy().astype(float)
        a2.fill_between(d, row + 0.1, row + 0.9, where=on > 0.5,
                        color=CH_COLOR[ch], alpha=0.9, step="mid")
        a2.text(-60, row + 0.5, ch, ha="right", va="center",
                fontsize=9, fontweight="bold", color=CH_COLOR[ch])
    a2.set_ylim(0, len(CH_ORDER)); a2.set_yticks([])
    a2.set_xlabel("distance along the lap (m)", fontsize=9)
    for sp in ["top", "right", "left"]:
        a2.spines[sp].set_visible(False)

    for ax_ in (a1, a2):
        for i, col in [(corner_i, "#00d084"), (open_i, "#00b4d8")]:
            ax_.axvline(d[i], color=col, lw=1.4, ls="--", alpha=0.9)
    a1.annotate("THE CORNER", (d[corner_i], 1.0), color="#00a86b",
                fontsize=8.5, fontweight="bold", ha="center")
    a1.annotate("THE STRAIGHT", (d[open_i], 1.0), color="#0096c7",
                fontsize=8.5, fontweight="bold", ha="center")
    plt.savefig(os.path.join(OUT, "fig2_channels.png"), dpi=160, bbox_inches="tight")
    plt.close()

    print("saved fig1_track_load.png and fig2_channels.png")


if __name__ == "__main__":
    make_figures()
