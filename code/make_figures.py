"""
Regenerate every figure in ../figures from the derived tables in ../data.

Run:
    python code/make_figures.py

Nothing here reads licensed third-party records. Every input is a derived
summary table produced by the APCOM experiment package and checked into
../data, so the figures are reproducible from this repository alone.

Temperatures plotted are A123-equivalent CELL SURFACE values from a fitted
lumped model. They are not measured or validated Sandvik Z50 pack temperatures.
"""
import os
import sys

# matplotlib may be vendored inside the research workspace rather than installed.
try:
    import matplotlib
except ImportError:  # pragma: no cover - environment fallback
    for cand in (
        r"C:\Users\athif\Documents\ChatGPT\BEV\ML_Forecasting_2026-10-25\lfp\vendor",
        r"C:\Users\athif\Documents\ChatGPT\BEV\APCOM_TR_Warning_2026-10-16\.deps",
    ):
        if os.path.isdir(cand):
            sys.path.insert(0, cand)
            break
    import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "derived")
MANIFEST = os.path.join(ROOT, "data", "manifest")
FIGS = os.path.join(ROOT, "figures")

# Derived tables are grouped by experiment. Resolve a bare filename against
# those subdirectories so the figures do not hard-code the layout.
_SEARCH = ("", "thermal", "experiment_a", "experiment_b")


def data_path(name):
    for sub in _SEARCH:
        candidate = os.path.join(DATA, sub, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "%s not found under %s. Run from the repository root; see data/README.md"
        % (name, DATA))
os.makedirs(FIGS, exist_ok=True)

# ---------------------------------------------------------------- frozen model
A_COEF = 4.344635339312832e-05   # K/(A^2 s)
B_COEF = 0.002655462788692412    # 1/s
TAU = 1.0 / B_COEF               # 376.58 s
T_AIR = 25.0

# worked example: native event Id 44, HS_EquipmentState, case C100_RR03
EV = dict(
    start_s=701.852626103349,
    end_s=1380.826476833902,
    energy_kwh=58.927842765108,
    capacity_kwh=354.0,
    t_start_c=25.000772630233,
)

# measured-cell held-out residual band, from the A123 fit the model is built on
RESID_LO, RESID_HI = 0.109, 0.117

# validated categorical palette, fixed order (never cycled)
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW, C_MAGENTA = (
    "#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7",
)
INK, INK2, INK3 = "#000000", "#333333", "#555555"
LINE, CAUTION, OK = "#cccccc", "#8c4a00", "#006644"

METHODS = [
    ("persistence", "Persistence", C_BLUE),
    ("linear_trend", "60 s trend", C_ORANGE),
    ("physics_hold", "Physics, held input", C_AQUA),
    ("ridge", "Ridge", C_YELLOW),
    ("hist_gradient_boosting", "Gradient boosting", C_MAGENTA),
]
HORIZON_LABEL = {60: "1 min", 120: "2 min", 300: "5 min", 600: "10 min"}

# Conventional journal styling: serif type, boxed axes, no decorative colour.
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Times New Roman", "Times"],
    "mathtext.fontset": "dejavuserif",
    "font.size": 9,
    "axes.edgecolor": "black",
    "axes.linewidth": 0.8,
    "axes.labelcolor": "black",
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "axes.titleweight": "normal",
    "axes.titlecolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "legend.fontsize": 8,
    "legend.frameon": True,
    "legend.framealpha": 1.0,
    "legend.edgecolor": "black",
    "legend.fancybox": False,
})


# Journals place the caption below the figure and do not repeat it as a title
# inside the image. Set this False to emit manuscript versions; the captions in
# docs/FIGURE_CAPTIONS.md then carry the text. Panel labels (A, B) are kept,
# since those are referenced from the caption body.
SHOW_TITLES = True


def save(fig, name):
    if not SHOW_TITLES:
        fig.suptitle("")
        if len(fig.axes) == 1:
            fig.axes[0].set_title("")
    path = os.path.join(FIGS, name)
    fig.savefig(path, dpi=170, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT).replace("\\", "/"))


def tidy(ax, bottom=True, left=True):
    """Conventional figures keep a full box; kept for call compatibility."""
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(True)


def case_label(row):
    return "%g kWh / %d%%" % (row["capacity_kwh"], int(row["rr_percent"]))


# ================================================== fig 03 nine-case demand
def fig_nine_case_demand():
    df = pd.read_csv(data_path("table2_nominal_reserve.csv"))
    df = df.sort_values(["capacity_kwh", "rr_percent"]).reset_index(drop=True)
    labels = [case_label(r) for _, r in df.iterrows()]
    x = np.arange(len(df))
    colors = [C_YELLOW] * 3 + [C_BLUE] * 3 + [C_AQUA] * 3

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    fig.suptitle("Figure 3. Mean power and cycle energy for the nine simulated configurations.",
                 fontsize=9, color="black")

    ax = axes[0]
    ax.bar(x, df["mean_power_kw"], color=colors, width=0.68, zorder=3)
    for xi, v in zip(x, df["mean_power_kw"]):
        ax.text(xi, v + 2.5, "%.1f" % v, ha="center", fontsize=7.4, color=INK2)
    ax.axhline(480, color=CAUTION, linewidth=1.2, linestyle="--", zorder=2)
    ax.text(len(df) - 0.4, 462, "480 kW continuous rating", ha="right",
            fontsize=7.6, color=CAUTION, va="top")
    ax.set_ylim(0, 520)
    ax.set_ylabel("Mean power over the window, kW")
    ax.set_title("Mean power", loc="left", fontsize=9)

    ax = axes[1]
    ax.bar(x, df["energy_per_complete_cycle_kwh"], color=colors, width=0.68, zorder=3)
    for xi, v in zip(x, df["energy_per_complete_cycle_kwh"]):
        ax.text(xi, v + 0.7, "%.2f" % v, ha="center", fontsize=7.4, color=INK2)
    ax.set_ylim(0, 84)
    ax.set_ylabel("Energy per recurring cycle, kWh")
    ax.set_title("Energy per cycle", loc="left", fontsize=9)

    for ax in axes:
        tidy(ax)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=7.8)
        ax.yaxis.grid(True, color=LINE, linewidth=0.8)
        ax.set_axisbelow(True)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c)
               for c in (C_YELLOW, C_BLUE, C_AQUA)]
    axes[1].legend(handles, ["283.2 kWh", "354.0 kWh", "424.8 kWh"],
                   loc="lower right", fontsize=7.8, ncol=3,
                   bbox_to_anchor=(1.0, -0.42))
    fig.text(0.055, -0.04,
             "Capacity, mass and available power vary together in the archived "
             "cases, so these compare whole vehicle configurations and do not "
             "isolate a pure capacity effect.",
             fontsize=7.8, color=INK3)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, "fig03_nine_case_demand.png")


# ================================================= fig 04 reserve windows
def fig_reserve_windows():
    df = pd.read_csv(data_path("table2_nominal_reserve.csv"))
    df = df.sort_values("window_end_min").reset_index(drop=True)
    labels = [case_label(r) for _, r in df.iterrows()]
    y = np.arange(len(df))
    colors = {283.2: C_YELLOW, 354.0: C_BLUE, 424.8: C_AQUA}
    cols = [colors[round(c, 1)] for c in df["capacity_kwh"]]

    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    ax.barh(y, df["window_end_min"], color=cols, height=0.66, zorder=3)
    for yi, (_, r) in zip(y, df.iterrows()):
        ax.text(r["window_end_min"] + 1.2, yi,
                "%.1f min   %d cycle%s" % (
                    r["window_end_min"], int(r["complete_recurring_cycles"]),
                    "" if r["complete_recurring_cycles"] == 1 else "s"),
                va="center", fontsize=8.0, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.4)
    ax.set_xlim(0, 128)
    ax.set_xlabel("Reserve-limited window, minutes")
    ax.set_title("Figure 4. Reserve-limited operating window by configuration.", loc="center", pad=10)
    tidy(ax, left=False)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.text(0.0, -0.05,
             "The reserve rule stops external analysis at 60% of nominal "
             "capacity, representing 80% to 20% state of charge. The raw run "
             "may continue past this point.",
             fontsize=7.8, color=INK3)
    fig.tight_layout()
    save(fig, "fig04_reserve_windows.png")


# ================================================== fig 05 worked example
def fig_worked_example():
    tr = pd.read_csv(data_path("trace_C100_RR03.csv"))
    dur = EV["end_s"] - EV["start_s"]
    p_kw = EV["energy_kwh"] / (dur / 3600.0)
    i_eq = 2.5 * p_kw / EV["capacity_kwh"]
    ss = A_COEF * i_eq ** 2 / B_COEF

    def closed_form(t):
        e = np.exp(-B_COEF * t)
        return T_AIR + (EV["t_start_c"] - T_AIR) * e + ss * (1.0 - e)

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))
    fig.suptitle("Figure 5. Worked thermal example for case C100_RR03.",
                 fontsize=9, color="black")

    # panel A: the whole case
    ax = axes[0]
    ax.plot(tr["time_s"] / 60.0, tr["temperature_c"], color=C_ORANGE, linewidth=1.6)
    ax.axvspan(EV["start_s"] / 60.0, EV["end_s"] / 60.0,
               color=C_BLUE, alpha=0.13, zorder=1)
    ax.text((EV["start_s"] + EV["end_s"]) / 120.0, 25.0655,
            "the worked\nevent", ha="center", fontsize=7.8, color=C_BLUE,
            fontweight="bold", linespacing=1.4)
    ax.set_xlabel("Time, minutes")
    ax.set_ylabel("Equivalent cell surface, $^\\circ$C")
    ax.set_title("A  Case C100_RR03, full window", loc="left", fontsize=9)
    tidy(ax)
    ax.yaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.text(0.98, 0.06, "air held at 25.000 $^\\circ$C", transform=ax.transAxes,
            ha="right", fontsize=7.6, color=INK3)

    # panel B: the single event, saved trace against closed form
    ax = axes[1]
    t = np.linspace(0, 2000, 900)
    ax.plot(t, closed_form(t), color=C_ORANGE, linewidth=2.0,
            label="closed form, current held")
    seg = tr[(tr["time_s"] >= EV["start_s"]) & (tr["time_s"] <= EV["end_s"])]
    ax.plot(seg["time_s"] - EV["start_s"], seg["temperature_c"], linestyle="none",
            marker="o", markersize=3.0, markerfacecolor="white",
            markeredgecolor=C_BLUE, markeredgewidth=0.9,
            label="saved trace samples")
    ax.axhline(T_AIR + ss, color=INK3, linewidth=1.0, linestyle="--")
    ax.text(1980, T_AIR + ss - 0.0028,
            "equilibrium  %.4f $^\\circ$C" % (T_AIR + ss),
            ha="right", va="top", fontsize=7.6, color=INK3)
    ax.axvline(TAU, color=LINE, linewidth=1.2, linestyle=":")
    ax.text(TAU + 24, 25.0035, "$\\tau$ = %.0f s" % TAU, fontsize=7.8, color=INK3)
    ax.axvline(dur, color=C_BLUE, linewidth=1.3)
    ax.text(dur + 24, 25.0015, "event ends\n%.1f s" % dur, fontsize=7.8,
            color=C_BLUE, linespacing=1.4)
    ax.set_xlabel("Seconds into the event, current held constant")
    ax.set_ylabel("Equivalent cell surface, $^\\circ$C")
    ax.set_title("B  One event: I = %.6f A" % i_eq, loc="left", fontsize=9)
    ax.legend(loc="lower right", fontsize=7.8)
    tidy(ax)
    ax.yaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)

    fig.text(0.055, -0.05,
             "The event uses %.6f kWh in %.3f s, giving %.3f kW, and an assumed "
             "equivalent current of %.6f A. The closed form lands on "
             "%.6f $^\\circ$C against a saved %.6f $^\\circ$C."
             % (EV["energy_kwh"], dur, p_kw, i_eq,
                closed_form(dur), 25.066656834106034),
             fontsize=7.8, color=INK3)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, "fig05_worked_example.png")


# ================================================ fig 06 nine-case rise/margin
def fig_nine_case_rise():
    df = pd.read_csv(data_path("table2_nominal_reserve.csv"))
    df = df.sort_values("peak_rise_c").reset_index(drop=True)
    colors = {283.2: C_YELLOW, 354.0: C_BLUE, 424.8: C_AQUA}
    cols = [colors[round(c, 1)] for c in df["capacity_kwh"]]

    fig, axes = plt.subplots(2, 1, figsize=(10.4, 5.0),
                             gridspec_kw={"height_ratios": [1, 1.25]})
    fig.suptitle("Figure 6. Peak surrogate temperature against the declared "
                 "screens, at full scale and magnified.",
                 fontsize=9, color="black")

    # panel A: full scale
    ax = axes[0]
    ax.scatter(df["peak_surface_c"], np.zeros(len(df)), s=70, c=cols,
               edgecolor="white", linewidth=1.2, zorder=4)
    ax.axvline(55, color=CAUTION, linewidth=1.4)
    ax.axvline(60, color=CAUTION, linewidth=1.4, linestyle="--")
    ax.text(55, 0.55, "55 $^\\circ$C\ndatasheet operating", ha="center",
            fontsize=7.6, color=CAUTION, linespacing=1.4)
    ax.text(60, 0.55, "60 $^\\circ$C\ndeclared study screen", ha="center",
            fontsize=7.6, color=CAUTION, linespacing=1.4)
    ax.annotate("", xy=(25, -0.45), xytext=(60, -0.45),
                arrowprops=dict(arrowstyle="<->", color=INK3, linewidth=1.0))
    ax.text(42.5, -0.75, "margin is 34.91 to 34.96 $^\\circ$C in every case",
            ha="center", fontsize=8.0, color=INK2)
    ax.set_xlim(24, 62)
    ax.set_ylim(-1.0, 1.2)
    ax.set_yticks([])
    ax.set_xlabel("Peak equivalent cell surface, $^\\circ$C")
    ax.set_title("A  Full scale: all nine cases are indistinguishable",
                 loc="left", fontsize=9)
    tidy(ax, left=False)

    # panel B: magnified
    ax = axes[1]
    y = np.arange(len(df))
    ax.barh(y, df["peak_rise_c"], color=cols, height=0.6, zorder=3)
    for yi, (_, r) in zip(y, df.iterrows()):
        ax.text(r["peak_rise_c"] + 0.0012, yi, "%.5f" % r["peak_rise_c"],
                va="center", fontsize=7.8, color=INK2, family="monospace")
    ax.set_yticks(y)
    ax.set_yticklabels([case_label(r) for _, r in df.iterrows()], fontsize=8.0)
    ax.set_xlim(0, 0.112)
    ax.set_xlabel("Peak rise above air, $^\\circ$C  (note the scale)")
    ax.set_title("B  Magnified about a thousandfold: a clean ordering appears",
                 loc="left", fontsize=9)
    tidy(ax, left=False)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c)
               for c in (C_YELLOW, C_BLUE, C_AQUA)]
    ax.legend(handles, ["283.2 kWh", "354.0 kWh", "424.8 kWh"],
              loc="lower right", fontsize=7.8, ncol=3)
    fig.text(0.055, -0.03,
             "Bigger packs run cooler and higher rolling resistance runs hotter. "
             "The ordering is real inside the model; its scale makes it "
             "operationally meaningless, and it sits below the model's own "
             "0.109 to 0.117 $^\\circ$C residual error.",
             fontsize=7.8, color=INK3)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save(fig, "fig06_nine_case_rise.png")


# ==================================================== fig 07 the noise floor
def fig_noise_floor():
    df = pd.read_csv(data_path("table4_pooled_metrics.csv"))
    horizons = [60, 120, 300, 600]

    fig, ax = plt.subplots(figsize=(10.6, 4.6))
    ax.axvspan(RESID_LO, RESID_HI, color=CAUTION, alpha=0.45, zorder=2)
    ax.text(RESID_HI * 1.12, 3.52,
            "measured-cell residual\n%.3f to %.3f $^\\circ$C" % (RESID_LO, RESID_HI),
            fontsize=8.2, color=CAUTION, fontweight="bold", va="center",
            linespacing=1.5)

    for row, h in enumerate(horizons):
        sub = df[df["horizon_s"] == h]
        for key, label, col in METHODS:
            v = float(sub[sub["method"] == key]["rmse_c"].iloc[0])
            ax.plot([v], [row], marker="o", markersize=9, color=col,
                    linestyle="none", markeredgecolor="white",
                    markeredgewidth=1.6, zorder=5,
                    label=label if row == 0 else None)

    ax.set_yticks(range(len(horizons)))
    ax.set_yticklabels([HORIZON_LABEL[h] for h in horizons], fontsize=9.5)
    ax.set_ylim(-0.6, 3.9)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(8e-4, 3e-1)
    ax.set_xlabel("Pooled RMSE, $^\\circ$C  (logarithmic; further left is better)")
    ax.set_title("Figure 7. Pooled forecast RMSE by method and horizon, with "
                 "the measured-cell residual band.", loc="center", pad=10)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8, which="major")
    ax.set_axisbelow(True)
    tidy(ax, left=False)

    ax.annotate("trend and physics are now\nworse than doing nothing",
                xy=(0.0539, 3.0), xytext=(0.075, 2.45),
                fontsize=8.0, color="black", linespacing=1.4,
                arrowprops=dict(arrowstyle="-|>", color="black", linewidth=0.8))
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.22), ncol=5, fontsize=8.4)
    fig.text(0.0, -0.17,
             "Pooled over nine leave-one-configuration-out holdouts. Separating "
             "methods by 0.003 $^\\circ$C inside a 0.11 $^\\circ$C uncertainty is "
             "arithmetic about a synthetic generator, not a physical measurement.",
             fontsize=7.8, color=INK3)
    fig.tight_layout()
    save(fig, "fig07_noise_floor.png")


# ============================================ fig 08 both metrics vs horizon
def fig_metrics_by_horizon():
    df = pd.read_csv(data_path("table4_pooled_metrics.csv"))
    horizons = [60, 120, 300, 600]
    xs = np.arange(len(horizons))

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.3), sharex=True)
    fig.suptitle("Figure 8. Pooled RMSE and MAE by forecast horizon.",
                 fontsize=9, color="black")

    for ax, metric, title in ((axes[0], "rmse_c", "A  RMSE"),
                              (axes[1], "mae_c", "B  MAE")):
        for key, label, col in METHODS:
            vals = [float(df[(df.horizon_s == h) & (df.method == key)][metric].iloc[0])
                    for h in horizons]
            ax.plot(xs, vals, marker="o", markersize=6, linewidth=2.0,
                    color=col, markeredgecolor="white", markeredgewidth=1.2,
                    label=label)
        ax.set_yscale("log")
        ax.set_xticks(xs)
        ax.set_xticklabels([HORIZON_LABEL[h] for h in horizons])
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_ylabel("Pooled %s, $^\\circ$C" % metric.split("_")[0].upper())
        ax.yaxis.grid(True, color=LINE, linewidth=0.8, which="major")
        ax.set_axisbelow(True)
        tidy(ax)

    axes[1].annotate("physics wins MAE\nat 1 minute",
                     xy=(0.0, 4.317e-4), xytext=(0.35, 1.05e-3),
                     fontsize=8.0, color="black", linespacing=1.4,
                     arrowprops=dict(arrowstyle="-|>", color="black", linewidth=0.8))
    axes[0].annotate("trend crosses above\npersistence",
                     xy=(3.0, 0.0539), xytext=(1.75, 0.075),
                     fontsize=8.0, color="black", linespacing=1.4,
                     arrowprops=dict(arrowstyle="-|>", color="black", linewidth=0.8))
    axes[0].legend(loc="upper left", bbox_to_anchor=(0.0, -0.18), ncol=5,
                   fontsize=8.4)
    fig.text(0.055, -0.13,
             "Gradient boosting leads on RMSE at all four horizons, but on MAE the "
             "held-input physics baseline wins at 1 minute. This is why the paper "
             "says boosting wins at 2, 5 and 10 minutes and not at 1.",
             fontsize=7.8, color=INK3)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save(fig, "fig08_metrics_by_horizon.png")


# ================================================== fig 09 rule response times
def fig_rule_response():
    df = pd.read_csv(data_path("table5_rule_response.csv"),
                     encoding="utf-8-sig")
    sets = [("Sheffield_all", "Sheffield cells\n27 records", C_AQUA),
            ("TUM_channels", "TUM module\n6 channels", C_YELLOW)]
    rules = ["fixed_45C", "fixed_50C", "fixed_55C", "fixed_60C",
             "rate_1C_min", "rate_2C_min", "rate_5C_min"]
    nice = {"fixed_45C": "> 45 $^\\circ$C", "fixed_50C": "> 50 $^\\circ$C",
            "fixed_55C": "> 55 $^\\circ$C", "fixed_60C": "> 60 $^\\circ$C",
            "rate_1C_min": "slope > 1 $^\\circ$C/min",
            "rate_2C_min": "slope > 2 $^\\circ$C/min",
            "rate_5C_min": "slope > 5 $^\\circ$C/min"}

    fig, ax = plt.subplots(figsize=(10.4, 4.6))
    y = np.arange(len(rules))
    off = 0.19
    for k, (sk, slabel, col) in enumerate(sets):
        sub = df[df["record_set"] == sk].set_index("rule")
        for i, r in enumerate(rules):
            row = sub.loc[r]
            lo, med, hi = (float(row["first_alarm_min_s"]),
                           float(row["first_alarm_median_s"]),
                           float(row["first_alarm_max_s"]))
            yy = y[i] + (off if k == 0 else -off)
            ax.plot([lo, hi], [yy, yy], color=col, linewidth=2.6,
                    solid_capstyle="round", zorder=3,
                    label=slabel if i == 0 else None)
            ax.plot([med], [yy], marker="|", markersize=13, color="white",
                    markeredgewidth=2.6, zorder=4)
            ax.plot([med], [yy], marker="|", markersize=10, color=col,
                    markeredgewidth=1.8, zorder=5)
            ax.text(hi * 1.14, yy, "%g-%g s" % (lo, hi), va="center",
                    fontsize=7.4, color=INK2, family="monospace")

    ax.set_yticks(y)
    ax.set_yticklabels([nice[r] for r in rules], fontsize=8.6)
    ax.set_xscale("log")
    ax.set_xlim(6, 6500)
    ax.set_xlabel("Time of first rule response, seconds (logarithmic). "
                  "Tick marks the median.")
    ax.set_title("Figure 9. First rule-response time on laboratory records.", loc="center", pad=10)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8, which="major")
    ax.set_axisbelow(True)
    tidy(ax, left=False)
    ax.legend(loc="lower right", fontsize=8.4)
    fig.text(0.0, -0.1,
             "These are RESPONSES TO RECORDED HEATING, not verified runaway "
             "detections. No independent, temperature-free onset reference with a "
             "bounded sensor clock exists in either archive, so lead time, misses "
             "and field false-alarm rate are reported as UNAVAILABLE.",
             fontsize=7.8, color=CAUTION)
    fig.tight_layout()
    save(fig, "fig09_rule_response.png")


# =============================================== fig 10 rules quiet on normal
def fig_rules_quiet():
    df = pd.read_csv(data_path("frozen_rule_summary.csv"))
    nom = df[df["set"] == "nominal"]
    sen = df[df["set"] == "sensitivity"]

    fig, ax = plt.subplots(figsize=(9.8, 3.6))
    groups = [("9 nominal trajectories", nom, C_BLUE),
              ("729 assumed variants", sen, C_ORANGE)]
    y = np.arange(2)
    for i, (label, sub, col) in enumerate(groups):
        screened = int(sub["trajectories_screened"].iloc[0])
        samples = int(sub["eligible_samples"].max())
        alarms = int(sub["trajectories_with_debounced_alarm"].sum())
        ax.barh([i], [samples], color=col, height=0.5, zorder=3)
        ax.text(samples * 1.03, i,
                "%s trajectories  |  %s eligible samples  |  "
                "%d alarms across all 7 rules"
                % (f"{screened:,}", f"{samples:,}", alarms),
                va="center", fontsize=8.4, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels([g[0] for g in groups], fontsize=9.0)
    ax.set_xscale("log")
    ax.set_xlim(1e4, 5e8)
    ax.set_xlabel("Eligible samples screened, logarithmic")
    ax.set_title("Figure 10. Frozen-rule screening of modelled normal trajectories.", loc="center", pad=10)
    ax.xaxis.grid(True, color=LINE, linewidth=0.8, which="major")
    ax.set_axisbelow(True)
    tidy(ax, left=False)
    fig.text(0.0, -0.14,
             "The denominator is modelled scenarios and samples, not field "
             "exposure. The nine nominal settings are a subset of the 729, not "
             "nine extra independent experiments.",
             fontsize=7.8, color=INK3)
    fig.tight_layout()
    save(fig, "fig10_rules_quiet.png")


if __name__ == "__main__":
    fig_nine_case_demand()
    fig_reserve_windows()
    fig_worked_example()
    fig_nine_case_rise()
    fig_noise_floor()
    fig_metrics_by_horizon()
    fig_rule_response()
    fig_rules_quiet()
    print("\nall figures written to", os.path.relpath(FIGS, ROOT))
