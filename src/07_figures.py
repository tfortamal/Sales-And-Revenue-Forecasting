"""Labelled PNG charts, one per insight (4_python_visuals/), and the README picks (images/).

Every chart reads the insight tables written by 06 (3_insight_tables/), so each PNG shows
exactly the numbers in its CSV. Two small inputs come from data/intermediate/: the back-test origins (forecast_backtest.csv) and
the model 04 selected (forecast_selected_model.txt).

Each chart has a takeaway title (the finding), a subtitle (what is shown), axis labels with
units, direct value labels where they help, and a footnote with the source and the "drink
sales only" caveat. Titles, subtitles, dates and the wording of every claim ("every", "despite",
"leads") are built from the data, so they stay true after a fresh download.

Font is Arial: on macOS matplotlib only finds a regular face for Helvetica Neue, so bold titles
would silently render regular.

Colours follow a colour-blind-safe palette: venue types keep one fixed colour everywhere;
growth vs decline is blue vs red (never green vs red); totals are grey. Growth components
(same-venue / new / acquired / closed) use their own colours so they never look like a
venue type. No dual axes.
"""
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from common import (ALCOHOL_SHARE_NOTE, BASE_YEAR, IMAGES, INTERMEDIATE, SELECTED_MODEL, TABLES, VISUALS,
                    money, pct)

TYPE_COLORS = {"Gentlemen's club": "#2a78d6", "Sports-bar restaurant": "#eb6834",
               "Latin-themed club": "#1baf7a", "Other bar / nightclub": "#898781"}
TYPE_ORDER = list(TYPE_COLORS)
IN_SENTENCE = {"Gentlemen's club": "gentlemen's club", "Sports-bar restaurant": "sports-bar restaurant",
               "Latin-themed club": "Latin-themed club", "Other bar / nightclub": "other bar / nightclub"}
UP, DOWN, TOTAL = "#2a78d6", "#e34948", "#898781"
INK, INK2, MUTED, GRID, SURFACE, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb", "#c3c2b7"
DIRECTION_COLORS = {"Growing": UP, "Declining": DOWN, "Stable": TOTAL}
# (colour, label text colour) per growth component; none of these is a venue-type colour.
COMPONENT_COLORS = {"Same-venue growth": ("#4a3aa7", "white"), "New venues (opened / other)": ("#eda100", INK),
                    "Acquired venues": ("#e87ba4", INK), "Closed venues": ("#898781", "white")}
MODEL_SHORT = {"ensemble": "ensemble", "ets": "exponential-smoothing", "prophet": "Prophet",
               "gbm": "gradient-boosting", "snaive": "same-month-last-year"}
MODEL_METHOD = {"ensemble": "ensemble of exponential smoothing, Prophet and gradient boosting per venue",
                "ets": "exponential smoothing per venue", "prophet": "Prophet per venue",
                "gbm": "one gradient-boosting model across all venues", "snaive": "same month last year per venue"}
CTX = {}   # dates and the selected model, filled in main()

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica Neue", "DejaVu Sans"],
    "text.parse_math": False,   # "$52.1M ... $56.4M" must print dollars, not switch to maths mode
    "font.size": 10, "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": AXIS,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.labelsize": 9.5, "legend.frameon": False, "legend.fontsize": 9,
})


# ---------------------------------------------------------------- helpers
money_m = mtick.FuncFormatter(lambda v, _: "$0" if v == 0 else f"{'−' if v < 0 else ''}${abs(v) / 1e6:,.0f}M")
money_k = mtick.FuncFormatter(lambda v, _: "$0" if v == 0 else f"${v / 1e3:,.0f}K")


def load(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(TABLES / name, **kw)


def finish(fig, name: str, title: str, subtitle: str, note: str = "") -> str:
    """Takeaway title + subtitle on top, source footnote at the bottom, then save."""
    w, h = fig.get_size_inches()
    sub_lines = subtitle.count("\n") + 1
    note_lines = 1 + bool(note)
    x = 0.12 / w
    fig.text(x, 1 - 0.14 / h, title, fontsize=14, fontweight="bold", color=INK, va="top")
    fig.text(x, 1 - 0.48 / h, subtitle, fontsize=10, color=INK2, va="top", linespacing=1.35)
    foot = CTX["source"] + ("\n" + note if note else "")
    fig.text(x, 0.1 / h, foot, fontsize=7.8, color=MUTED, va="bottom", linespacing=1.4)
    top = 1 - (0.62 + 0.19 * sub_lines) / h
    bottom = (0.2 + 0.16 * note_lines) / h
    fig.tight_layout(rect=(0, bottom, 1, top))
    fig.savefig(VISUALS / name, dpi=160)
    plt.close(fig)
    print(f"  {name}")
    return name


def clean_axis(ax, grid_axis: str = "y") -> None:
    ax.grid(axis="x" if grid_axis == "y" else "y", visible=False)
    ax.tick_params(length=0)


def kpi(name: str, col: str = "Display Text"):
    return load("p1_kpis.csv").set_index("KPI").loc[name, col]


# ---------------------------------------------------------------- charts
def group_trend():
    t = load("p1_group_trend_and_forecast.csv", parse_dates=["Month"])
    t = t[t["Month"] >= "2015-01-01"]
    s = {k: g.set_index("Month")["Drink Revenue"] for k, g in t.groupby("Series")}
    y = load("p1_group_yearly_totals.csv").groupby(["Year", "Year Status"])["Drink Revenue"].sum().reset_index()
    full = y[y["Year Status"] == "Actual"]
    peak = full.loc[full["Drink Revenue"].idxmax()]
    latest, fy = CTX["latest"], CTX["fy"]
    outlook = {"Stable": "flat", "Declining": "lower", "Growing": "higher"}[kpi("Next-year forecast (base)", "Direction")]
    now = {"Declining": "is falling", "Stable": "is flat", "Growing": "is growing again"}[
        kpi("Growth vs prior 12 months", "Direction")]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-01"), color=GRID, alpha=0.6, linewidth=0)
    ax.fill_between(s["Forecast low (80%)"].index, s["Forecast low (80%)"], s["Forecast high (80%)"],
                    color=UP, alpha=0.15, linewidth=0, label="Forecast 80% range")
    ax.plot(s["Actual"].index, s["Actual"], color=UP, linewidth=2, label="Actual")
    ax.plot(s["Forecast"].index, s["Forecast"], color=UP, linewidth=2, linestyle=(0, (4, 3)), label="Forecast (base)")
    ax.set_ylim(0, s["Forecast high (80%)"].max() * 1.25)
    # COVID label sits at the foot of the shaded band, clear of the legend.
    ax.text(pd.Timestamp("2020-06-15"), ax.get_ylim()[1] * 0.04, "COVID\nclosures", fontsize=8.5, color=INK2, va="bottom")
    ax.annotate(f"Last 12 months: {kpi('Drink revenue, last 12 months')}\n"
                f"({kpi('Growth vs prior 12 months')} vs the 12 before)",
                xy=(latest, s["Actual"].iloc[-1]), xytext=(latest - pd.DateOffset(months=41), 1.9e6),
                fontsize=9.5, color=INK, va="top", arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.text(latest - pd.DateOffset(months=2), 3.2e6,
            f"{fy} forecast: {kpi('Next-year forecast (base)')}\n"
            f"80% range {kpi('Next-year forecast low (80%)')}–{kpi('Next-year forecast high (80%)')}",
            fontsize=9.5, color=INK, va="top")
    ax.yaxis.set_major_formatter(money_m)
    ax.set_ylabel("Monthly drink revenue (USD)")
    ax.set_xlabel("Month")
    ax.legend(loc="upper left", ncol=3)
    clean_axis(ax)
    nxt = latest + pd.DateOffset(months=1)
    return finish(fig, "01_group_revenue_trend_and_forecast.png",
                  f"Drink revenue peaked in {int(peak['Year'])} ({money(peak['Drink Revenue'])}) and {now}; "
                  f"{fy} is forecast {outlook} at {kpi('Next-year forecast (base)')}",
                  f"Monthly drink sales across RCI's Texas venues: actual Jan 2015 to {latest:%b %Y}, "
                  f"base forecast {nxt:%b %Y} to Dec {fy} with its 80% range.",
                  f"Forecast: {MODEL_METHOD[CTX['model']]}, back-tested against 'same month last year'.")


def waterfall(wf: pd.DataFrame, name: str, title: str, subtitle: str, note: str = ""):
    wf = wf[wf["Detail"] == "By component"].sort_values("Step Order")
    fig, ax = plt.subplots(figsize=(10, 5.2))
    colors = {"Total": TOTAL, "Increase": UP, "Decrease": DOWN}
    top = wf[["Bar Start", "Bar End"]].max(axis=1).max()
    pad = top * 0.015
    for i, (_, r) in enumerate(wf.iterrows()):
        lo, hi = sorted([r["Bar Start"], r["Bar End"]])
        ax.bar(i, hi - lo, bottom=lo, color=colors[r["Kind"]], width=0.62)
        ax.text(i, hi + pad, r["Change Label"], ha="center", va="bottom", fontsize=10,
                fontweight="bold" if r["Kind"] == "Total" else "normal", color=INK)
        if i < len(wf) - 1:   # connector to the next bar
            ax.plot([i + 0.31, i + 0.69], [r["Bar End"]] * 2, color=MUTED, linewidth=0.8, linestyle=":")
    labels = [s.replace(" (opened / other)", "\n(opened / other)").replace("Same-venue growth", "Same-venue\ngrowth")
              .replace("Acquired venues", "Acquired\nvenues").replace("Closed venues", "Closed\nvenues")
              .replace("Prior 12 months", "Prior\n12 months").replace("Last 12 months", "Last\n12 months")
              for s in wf["Step"]]
    ax.set_xticks(range(len(wf)), labels)
    ax.set_ylim(0, top * 1.12)
    ax.yaxis.set_major_formatter(money_m)
    ax.set_ylabel("Drink revenue over the period (USD)")
    clean_axis(ax)
    return finish(fig, name, title, subtitle, note)


def growth_sources():
    wf = load("p1_growth_bridge_waterfall.csv")
    wf = wf[wf["Is Long Run"]]
    comp = wf[wf["Detail"] == "By component"].set_index("Step")
    w, v = comp["Change Label"], comp["Change"]
    y1 = CTX["last_full"]
    added = [f"{name} ({w[step]})" for step, name in (("Acquired venues", "Acquisitions"),
                                                      ("New venues (opened / other)", "new venues"))
             if v.get(step, 0) > 0]
    if added and v.get("Same-venue growth", 0) < 0:
        title = f"{' and '.join(added)}, not existing venues, drove growth since {BASE_YEAR}"
    else:
        title = f"Drink revenue went from {w[str(BASE_YEAR)]} in {BASE_YEAR} to {w[str(y1)]} in {y1}"
    title = title[0].upper() + title[1:]
    return waterfall(wf, f"02_growth_sources_since_{BASE_YEAR}.png", title,
                     f"Annual drink revenue, {BASE_YEAR} vs {y1}, and what changed in between. Same-venue = venues "
                     f"trading in both years of each\nyear-on-year step; new, acquired and closed venues are counted in "
                     f"the year they joined or left.",
                     f"Yearly bridges {BASE_YEAR + 1} to {y1} are summed, so every venue's change is counted exactly once.")


def ttm_bridge():
    wf = load("p1_growth_bridge_waterfall.csv")
    wf = wf[wf["Is Latest"]]
    comp = wf[wf["Detail"] == "By component"].set_index("Step")
    w, v = comp["Change Label"], comp["Change"]
    no_acq = "" if "Acquired venues" in w.index else " (no acquisitions in this window)"
    growth = kpi("Growth vs prior 12 months", "Value")
    verb = "fell" if growth < 0 else "rose"
    # Name the components that pushed in the same direction as the total.
    parts = {"Same-venue growth": ("existing venues", "lost", "added"), "Closed venues": ("closures", "cost", "added"),
             "New venues (opened / other)": ("new venues", "cost", "added"), "Acquired venues": ("acquisitions", "cost", "added")}
    drivers = [f"{who} {lose if growth < 0 else gain} {w[step].lstrip('−+')}"
               for step, (who, lose, gain) in parts.items() if step in v.index and v[step] * growth > 0]
    title = f"The last 12 months {verb} {kpi('Growth vs prior 12 months').lstrip('−+')}" + \
        (f": {' and '.join(drivers[:2])}" if drivers else "")
    return waterfall(wf, "03_last_12_months_bridge.png", title,
                     f"Drink revenue, {CTX['ttm_span']} vs the 12 months before, split by where the change came "
                     f"from{no_acq}.")


def type_contribution():
    c = load(f"p3_type_growth_sources_since_{BASE_YEAR}.csv")
    net = c.groupby("Venue Type")["Change"].sum()
    y1 = CTX["last_full"]
    order = ["Gentlemen's club", "Latin-themed club", "Sports-bar restaurant", "Other bar / nightclub"]
    fig, ax = plt.subplots(figsize=(11, 5))
    for row, vtype in enumerate(order):
        pos = neg = 0.0
        for comp, (color, text_color) in COMPONENT_COLORS.items():
            v = c.loc[(c["Venue Type"] == vtype) & (c["Component"] == comp), "Change"].sum()
            if v == 0:   # component absent for this type
                continue
            left = pos if v > 0 else neg
            ax.barh(row, v, left=left, color=color, height=0.58, edgecolor=SURFACE, linewidth=1.5, label=comp)
            if abs(v) >= 2.5e6:   # label segments wide enough to hold text
                ax.text(left + v / 2, row, money(v, signed=True), ha="center", va="center", fontsize=8.5,
                        color=text_color)
            pos, neg = (pos + v, neg) if v > 0 else (pos, neg + v)
        ax.text(pos + 4e5, row, f"net {money(net[vtype], signed=True)}", va="center", fontsize=10, fontweight="bold")
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_yticks(range(len(order)), order)
    ax.invert_yaxis()
    ax.set_xlim(c.groupby("Venue Type")["Change"].apply(lambda s: s[s < 0].sum()).min() - 2e6,
                c.groupby("Venue Type")["Change"].apply(lambda s: s[s > 0].sum()).max() + 4.5e6)
    ax.xaxis.set_major_formatter(money_m)
    ax.set_xlabel(f"Change in annual drink revenue, {BASE_YEAR} to {y1} (USD)")
    handles, labels = ax.get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    ax.legend([uniq[k] for k in COMPONENT_COLORS if k in uniq], [k for k in COMPONENT_COLORS if k in uniq],
              ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    clean_axis(ax, "x")
    by_comp = c.groupby("Component")["Change"].sum()
    acquired_types = set(c.loc[(c["Component"] == "Acquired venues") & (c["Change"] > 0), "Venue Type"])
    lead = ("Acquired clubs drove growth" if by_comp.idxmax() == "Acquired venues"
            and "Sports-bar restaurant" not in acquired_types else f"{by_comp.idxmax()} drove the most growth")
    sb_net = net["Sports-bar restaurant"]
    sb_new = c.loc[(c["Venue Type"] == "Sports-bar restaurant") & (c["Component"] == "New venues (opened / other)"),
                   "Change"].sum()
    link = "despite" if sb_net < 0 < sb_new else "with"
    return finish(fig, f"04_change_by_venue_type_since_{BASE_YEAR}.png",
                  f"{lead}; sports bars ended {money(sb_net, signed=True)} {link} "
                  f"{money(sb_new, signed=True)} from openings",
                  f"Change in annual drink revenue from {BASE_YEAR} to {y1} for each venue type, split by where it came "
                  f"from. Bars right of zero added revenue,\nbars left of it lost revenue; the bold figure is the net change.",
                  f"Segments under $2.5M are unlabelled; see p3_type_growth_sources_since_{BASE_YEAR}.csv for every value.")


def revenue_by_type():
    y = load("p1_revenue_by_type_yearly.csv")
    y1 = CTX["last_full"]
    y = y[(y["Revenue Basis"] == "Drink sales (reported)") & y["Year"].between(2012, y1)]
    p = y.pivot(index="Year", columns="Venue Type", values="Revenue").fillna(0)[TYPE_ORDER]
    sb_leads = p["Sports-bar restaurant"] > p["Gentlemen's club"]
    lead_sb = p.index[sb_leads]
    gc_back = p.index[(p.index > lead_sb.max()) & ~sb_leads]
    fig, ax = plt.subplots(figsize=(11, 5.4))
    bottom = np.zeros(len(p))
    for vtype in TYPE_ORDER:
        ax.bar(p.index, p[vtype], bottom=bottom, color=TYPE_COLORS[vtype], width=0.72, label=vtype,
               edgecolor=SURFACE, linewidth=1)
        bottom += p[vtype].values
    for x, v in zip(p.index, bottom):
        ax.text(x, v + 6e5, money(v), ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(p.index, [str(i) for i in p.index])
    ax.set_ylim(0, bottom.max() * 1.18)
    ax.yaxis.set_major_formatter(money_m)
    ax.set_ylabel("Annual drink revenue (USD)")
    ax.legend(ncol=4, loc="upper left")
    clean_axis(ax)
    title = (f"Sports bars led from {lead_sb.min()} to {lead_sb.max()}; after club acquisitions, gentlemen's clubs "
             f"lead since {gc_back.min()}" if len(gc_back)
             else "Annual drink revenue by venue type")
    return finish(fig, "05_revenue_by_venue_type_over_time.png", title,
                  f"Annual drink revenue by venue type, 2012 to {y1} (full years only; {CTX['latest'].year} is partial "
                  f"so it is left out). Total above each bar.",
                  "2020 was cut by COVID closures.")


def type_share():
    rb = load("p3_type_revenue_by_basis.csv")
    d = rb[rb["Revenue Basis"] == "Drink sales (reported)"].set_index("Venue Type").loc[TYPE_ORDER]
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    wedges, _ = ax.pie(d["TTM Revenue"], colors=[TYPE_COLORS[t] for t in d.index], startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.38, edgecolor=SURFACE, linewidth=2))
    for wdg, (vtype, r) in zip(wedges, d.iterrows()):
        ang = np.deg2rad((wdg.theta1 + wdg.theta2) / 2)
        x, y = np.cos(ang), np.sin(ang)
        n = int(r["Active Venues"])
        ax.annotate(f"{vtype}\n{r['Share Label']} · {r['TTM Revenue Label']} · {n} venue{'s' if n != 1 else ''}",
                    xy=(0.82 * x, 0.82 * y), xytext=(1.22 * x, 1.18 * y), fontsize=9.5, color=INK,
                    ha="left" if x >= 0 else "right", va="center",
                    arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.text(0, 0.06, money(d["TTM Revenue"].sum()), ha="center", va="center", fontsize=17, fontweight="bold")
    ax.text(0, -0.14, "last 12 months", ha="center", va="center", fontsize=9, color=INK2)
    ax.set_aspect("equal")
    ax.set_xlim(-1.9, 1.9)
    ax.set_ylim(-1.35, 1.35)
    top2 = d["Share of Group (TTM)"].nlargest(2)
    plural = {"Gentlemen's club": "Gentlemen's clubs", "Sports-bar restaurant": "sports bars",
              "Latin-themed club": "Latin-themed clubs", "Other bar / nightclub": "other bars"}
    first = plural[top2.index[0]]
    return finish(fig, "06_revenue_share_by_venue_type.png",
                  f"{first[0].upper() + first[1:]} ({pct(top2.iloc[0], signed=False)}) and {plural[top2.index[1]]} "
                  f"({pct(top2.iloc[1], signed=False)}) bring in "
                  f"{'most' if top2.sum() > 0.5 else 'the largest shares of'} drink sales",
                  f"Share of drink revenue by venue type, last 12 months ({CTX['ttm_span']}), with active venues per type.")


def revenue_per_venue():
    rb = load("p3_type_revenue_by_basis.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, sharex=True)
    for ax, basis in zip(axes, ["Drink sales (reported)", "Est. total revenue"]):
        d = rb[rb["Revenue Basis"] == basis].set_index("Venue Type").loc[TYPE_ORDER[::-1]]
        ax.barh(d.index, d["Avg Monthly Revenue per Venue"], color=[TYPE_COLORS[t] for t in d.index], height=0.6)
        for i, v in enumerate(d["Avg Monthly Revenue per Venue"]):
            ax.text(v + 6e3, i, money(v), va="center", fontsize=10, color=INK)
        ax.set_title(basis, loc="left", fontsize=11, fontweight="bold", color=INK2)
        ax.xaxis.set_major_formatter(money_k)
        ax.set_xlabel("Average monthly revenue per trading venue (USD)")
        clean_axis(ax, "x")
    axes[0].set_xlim(0, rb["Avg Monthly Revenue per Venue"].max() * 1.2)
    est = rb[rb["Revenue Basis"] == "Est. total revenue"].set_index("Venue Type")["Avg Monthly Revenue per Venue"]
    return finish(fig, "07_revenue_per_venue_by_type.png",
                  f"On estimated total revenue, a {IN_SENTENCE[est.idxmax()]} earns the most per venue "
                  f"(about {money(est.max())} a month)",
                  "Average monthly revenue per trading venue, last 12 months. Left: reported drink sales. "
                  "Right: estimated total revenue =\ndrink sales / alcohol's share of segment revenue "
                  f"({ALCOHOL_SHARE_NOTE}; RCI FY2024 10-K), adding back door and dance income.",
                  "Estimated total revenue is an estimate: it assumes each venue matches its segment's alcohol share.")


def venue_yoy():
    g = load("p2_venue_growth_active.csv").sort_values("YoY Growth %")
    fig, ax = plt.subplots(figsize=(10, 0.3 * len(g) + 2.6))
    ax.barh(g["Venue"], g["YoY Growth %"], color=g["Direction"].map(DIRECTION_COLORS), height=0.66)
    for yv, (v, lab, ch) in enumerate(zip(g["YoY Growth %"], g["YoY Label"], g["YoY Change Label"])):
        ax.text(v + (0.012 if v >= 0 else -0.012), yv, f"{lab} ({ch})", va="center",
                ha="left" if v >= 0 else "right", fontsize=8, color=INK2)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_xlim(g["YoY Growth %"].min() - 0.22, g["YoY Growth %"].max() + 0.25)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Change in drink revenue, last 12 months vs the 12 months before (%)")
    ax.tick_params(axis="y", labelsize=8.5)
    counts = g["Direction"].value_counts()
    handles = [plt.Rectangle((0, 0), 1, 1, color=DIRECTION_COLORS[d]) for d in ("Growing", "Stable", "Declining")]
    ax.legend(handles, [f"{d} ({counts.get(d, 0)})" for d in ("Growing", "Stable", "Declining")],
              loc="lower right")
    clean_axis(ax, "x")
    below = int((g["YoY Growth %"] < 0).sum())
    return finish(fig, "08_venue_growth_last_12_months.png",
                  f"{counts.get('Declining', 0)} of {len(g)} venues are down more than 5% on a year ago "
                  f"({below} are below last year)",
                  f"Drink revenue change per active venue, {CTX['ttm_span']} vs the 12 months before (venues with 2 full "
                  f"years of history).\nGrowing / Declining = up / down more than 5%; Stable = within ±5%. Labels show "
                  f"the % and $ change.")


def top_venues():
    s = load("p2_venue_scorecard.csv")
    t = s[s["Top 10 (TTM)"]].sort_values("TTM Drink Revenue")
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.barh(t["Venue"], t["TTM Drink Revenue"], color=t["Venue Type"].map(TYPE_COLORS), height=0.62)
    for yv, (v, sh) in enumerate(zip(t["TTM Drink Revenue"], t["Share of Group (TTM)"])):
        ax.text(v + 1.2e5, yv, f"{money(v)} ({pct(sh, 0, signed=False)} of group)", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, t["TTM Drink Revenue"].max() * 1.3)
    ax.xaxis.set_major_formatter(money_m)
    ax.set_xlabel("Drink revenue, last 12 months (USD)")
    present = [v for v in TYPE_ORDER if v in set(t["Venue Type"])]
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=TYPE_COLORS[v]) for v in present], present, loc="lower right")
    clean_axis(ax, "x")
    lead = t.iloc[-1]
    return finish(fig, "09_top_10_venues.png",
                  f"{lead['Venue'].replace(' – ', ' ')} alone brings in {pct(lead['Share of Group (TTM)'], 0, signed=False)} "
                  f"of drink sales; the top 10 bring in {pct(t['Share of Group (TTM)'].sum(), 0, signed=False)}",
                  f"The 10 biggest venues by drink revenue, last 12 months ({CTX['ttm_span']}), coloured by venue type.")


def ramp():
    r = load("p3_ramp_curves.csv")
    r = r[r["Show In Chart"]]
    col = "Median Monthly Drink Revenue (3-month smoothed)"
    fig, ax = plt.subplots(figsize=(10, 5))
    ends = []
    for vtype in ["Gentlemen's club", "Sports-bar restaurant", "Latin-themed club"]:
        d = r[r["Venue Type"] == vtype].set_index("Months Since Joining")[col]
        ax.plot(d.index, d.values, color=TYPE_COLORS[vtype], linewidth=2)
        n = int(r.loc[r["Venue Type"] == vtype, "Venues in Sample"].max())
        ends.append([d.values[-1], d.index[-1], f"{vtype} (up to {n} venues)", d])
    ends.sort(key=lambda e: e[0])
    gap = 14e3
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    for yv, x, label, _ in ends:
        ax.text(x + 0.5, yv, label, fontsize=9, color=INK2, va="center")
    sb = next(e[3] for e in ends if e[2].startswith("Sports"))
    ax.annotate(f"Opening month {money(sb.iloc[0])}", xy=(sb.index[0], sb.iloc[0]), xytext=(7.5, sb.iloc[0] - 10e3),
                fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    low_m = sb.loc[12:].idxmin()
    ax.annotate(f"Month {low_m}: {money(sb.loc[low_m])}", xy=(low_m, sb.loc[low_m]),
                xytext=(low_m + 1, sb.loc[low_m] + 32e3), fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.set_xlim(1, r["Months Since Joining"].max() + 11)   # room for the end labels
    ax.set_ylim(0, r[col].max() * 1.08)
    ax.set_xticks([1, 6, 12, 18, 24, 30])
    ax.yaxis.set_major_formatter(money_k)
    ax.set_xlabel("Months since the venue joined RCI (opened or acquired)")
    ax.set_ylabel("Median monthly drink revenue (USD)")
    clean_axis(ax)
    drop = sb.loc[low_m] / sb.iloc[0] - 1
    gc = next(e[3] for e in ends if e[2].startswith("Gentlemen"))
    gc_trend = "gentlemen's clubs build up" if gc.iloc[-1] > gc.iloc[0] else "gentlemen's clubs stay flat or fade"
    sb_text = (f"New sports bars open strong, then fall {pct(drop, signed=False)} by month {low_m}" if drop < 0
               else "New sports bars hold their opening level")
    return finish(fig, "10_ramp_up_curves.png", f"{sb_text}; {gc_trend}",
                  "Median monthly drink revenue by months since joining RCI, venues added since 2008 "
                  "(3-month smoothing; shown while 3+ venues are in the sample).")


def acquisitions():
    a = load("p3_acquisitions.csv")
    g = a[a["Acquisition Kind"] == "Going concern"].sort_values("Uplift %")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    y = np.arange(len(g))
    ax.barh(y + 0.19, g["Avg Monthly Drinks: 12m Before"], height=0.36, color=TOTAL, label="12 months before RCI")
    ax.barh(y - 0.19, g["Avg Monthly Drinks: 12m After"], height=0.36, color=UP, label="12 months after RCI")
    for yi, (b, af, lab) in enumerate(zip(g["Avg Monthly Drinks: 12m Before"], g["Avg Monthly Drinks: 12m After"], g["Uplift Label"])):
        ax.text(b + 8e3, yi + 0.19, money(b), va="center", fontsize=8.5, color=INK2)
        ax.text(af + 8e3, yi - 0.19, f"{money(af)}  ({lab})", va="center", fontsize=9, color=INK, fontweight="bold")
    ax.set_yticks(y, [f"{v}\n(acquired {d[:7]})" for v, d in zip(g["Venue"], g["Acquired"])])
    ax.set_xlim(0, g["Avg Monthly Drinks: 12m After"].max() * 1.3)
    ax.xaxis.set_major_formatter(money_k)
    ax.set_xlabel("Average monthly drink revenue (USD)")
    ax.legend(loc="lower right")
    clean_axis(ax, "x")
    n_up = int((g["Uplift %"] > 0).sum())
    who = "Every going-concern acquisition" if n_up == len(g) else f"{n_up} of {len(g)} going-concern acquisitions"
    return finish(fig, "11_acquisitions_before_vs_after.png",
                  f"{who} sold more drinks after RCI took over "
                  f"({g['Uplift Label'].iloc[0]} to {g['Uplift Label'].iloc[-1]})",
                  "Average monthly drink revenue in the 12 months before vs after RCI took over "
                  "(handover month excluded), going-concern deals only.",
                  f"{len(g)} going-concern deals; {len(a) - len(g)} clubs bought while dormant are excluded (no meaningful 'before'). "
                  "Part of a jump may reflect rebranding or the previous owner's reporting.")


def seasonality():
    s = load("p2_seasonality_by_type.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    peaks = {}
    for vtype in TYPE_ORDER:
        d = s[s["Venue Type"] == vtype].sort_values("Month Number")
        ax.plot(d["Month Number"], d["vs Average Month"], color=TYPE_COLORS[vtype], linewidth=2, marker="o",
                markersize=4, label=vtype)
        peaks[vtype] = d.loc[d["vs Average Month"].idxmax(), "Month Name"]
    ax.axhline(0, color=INK2, linewidth=1)
    ax.text(12.35, 0, "average\nmonth", fontsize=8.5, color=INK2, va="center", ha="left")
    ax.set_xlim(0.6, 13.1)
    ax.set_xticks(range(1, 13), s.drop_duplicates("Month Number").sort_values("Month Number")["Month Name"])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Drink revenue vs an average month (%)")
    ax.legend(ncol=4, loc="upper right")
    ax.set_ylim(s["vs Average Month"].min() - 0.03, s["vs Average Month"].max() + 0.07)
    clean_axis(ax)
    busiest = pd.Series(peaks).value_counts().idxmax()
    with_peak = [t for t, m in peaks.items() if m == busiest]
    others = [f"{IN_SENTENCE[t]} {m}" for t, m in peaks.items() if m != busiest]
    lift = s[(s["Month Name"] == busiest) & s["Venue Type"].isin(with_peak)]["vs Average Month"]
    month_name = pd.Timestamp(f"2000-{busiest}-01").strftime("%B")
    title = (f"{month_name} is the busiest month for {len(with_peak)} of {len(peaks)} venue types "
             f"({pct(lift.min())} to {pct(lift.max())} vs an average month)")
    sub_extra = f" Peak for the rest: {', '.join(others)}." if others else ""
    return finish(fig, "12_seasonality_by_venue_type.png", title,
                  "Average drink revenue in each calendar month relative to the venue's own yearly average, by venue type "
                  "(full years only,\nCOVID months excluded)." + sub_extra,
                  "'Other bar / nightclub' is a single venue today, so its line is noisier.")


def drinks_mix():
    m = load("p2_drinks_mix_by_type.csv")
    yr = CTX["last_full"]
    m = m[m["Year"] == yr]
    drinks = {"Liquor": "#52514e", "Beer": "#898781", "Wine": "#c3c2b7"}
    fig, ax = plt.subplots(figsize=(10, 4.4))
    order = TYPE_ORDER[::-1]
    for row, vtype in enumerate(order):
        left = 0.0
        for drink, color in drinks.items():
            v = m[(m["Venue Type"] == vtype) & (m["Drink"] == drink)]["Share of Drinks"].iat[0]
            ax.barh(row, v, left=left, color=color, height=0.6, edgecolor=SURFACE, linewidth=1.5,
                    label=drink if row == 0 else None)
            if v >= 0.05:
                ax.text(left + v / 2, row, pct(v, 0, signed=False), ha="center", va="center", fontsize=9.5,
                        color="white" if drink != "Wine" else INK)
            left += v
    ax.set_yticks(range(len(order)), order)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(f"Share of drink revenue, {yr} (%)")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    clean_axis(ax, "x")
    lat = m[m["Venue Type"] == "Latin-themed club"].set_index("Drink")["Share of Drinks"]
    top_drink = m.loc[m.groupby("Venue Type")["Share of Drinks"].idxmax(), "Drink"]
    lead = ("Liquor leads at every venue type" if (top_drink == "Liquor").all()
            else "Liquor leads at " + f"{int((top_drink == 'Liquor').sum())} of {len(top_drink)} venue types")
    beer_vs = "nearly as much beer" if lat["Beer"] >= 0.8 * lat["Liquor"] else "a lot of beer"
    return finish(fig, "13_drinks_mix_by_venue_type.png",
                  f"{lead}; Latin clubs sell {beer_vs} ({pct(lat['Beer'], 0, signed=False)}) "
                  f"as liquor ({pct(lat['Liquor'], 0, signed=False)})" if beer_vs.startswith("nearly") else
                  f"{lead}; Latin clubs' drinks are {pct(lat['Beer'], 0, signed=False)} beer, "
                  f"{pct(lat['Liquor'], 0, signed=False)} liquor",
                  f"Liquor, beer and wine as a share of each venue type's drink revenue, {yr} (latest full year). "
                  f"A higher liquor share usually means higher spend per guest.",
                  "Shares under 5% are unlabelled (sports bars sell almost no wine).")


def forecast_accuracy():
    f = load("p4_forecast_accuracy.csv").sort_values("Sort Order", ascending=False)
    colors = f["Model Role"].map({"Selected": UP, "Baseline": INK2, "Other": AXIS})
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.barh(f["Model"], f["Venue-level Error (WAPE)"], color=colors, height=0.6)
    for yv, (v, lab, role) in enumerate(zip(f["Venue-level Error (WAPE)"], f["Venue Error Label"], f["Model Role"])):
        ax.text(v + 0.003, yv, lab + ("  selected" if role == "Selected" else "  baseline" if role == "Baseline" else ""),
                va="center", fontsize=9.5, color=INK, fontweight="bold" if role != "Other" else "normal")
    ax.set_xlim(0, f["Venue-level Error (WAPE)"].max() * 1.3)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Venue-level forecast error, WAPE (%) - lower is better")
    clean_axis(ax, "x")
    sel = f[f["Model Role"] == "Selected"].iloc[0]
    base = f[f["Is Baseline"]].iloc[0]
    origins = sorted(pd.to_datetime(pd.read_csv(INTERMEDIATE / "forecast_backtest.csv")["origin"].unique()))
    names = ", ".join(f"{o:%b %Y}" for o in origins[:-1]) + f" and {origins[-1]:%b %Y}"
    return finish(fig, "14_forecast_accuracy_vs_baseline.png",
                  (f"The {MODEL_SHORT[CTX['model']]} forecast cuts venue-level error from {base['Venue Error Label']} "
                   f"to {sel['Venue Error Label']}" if CTX["model"] != "snaive"
                   else f"No model beat 'same month last year' ({base['Venue Error Label']} venue-level error)"),
                  f"Back-test: each model forecast every venue 12 months ahead from {names} using only data known then.\n"
                  f"WAPE = total absolute error / total actual sales, averaged over the {len(origins)} origins. "
                  f"Selected model's average 12-month group error: {sel['Abs Error Label']}.")


def scenarios():
    s = load("p4_scenario_summary.csv").sort_values("Sort Order", ascending=False)
    est = s["Current-Year Estimate"].iat[0]
    fy, cy = CTX["fy"], CTX["cy"]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    colors = [TOTAL if g == "Core" else UP for g in s["Scenario Group"]]
    ax.barh(s["Scenario"], s["Forecast Drink Revenue"], color=colors, height=0.6)
    for yv, (v, lab) in enumerate(zip(s["Forecast Drink Revenue"], s["Display Label"])):
        # A label that would straddle the current-year line starts just right of it instead.
        x = est + 2.5e5 if v < est < v + 3.2e6 else v + 2.5e5
        ax.text(x, yv, lab, va="center", fontsize=9.5, color=INK)
    ax.axvline(est, color=INK2, linewidth=1, linestyle=(0, (3, 3)), zorder=1)
    ax.text(est + 1.5e5, len(s) - 0.45, f"{cy} estimate {money(est)}", fontsize=8.5, color=INK2, ha="left")
    ax.set_xlim(40e6, s["Forecast Drink Revenue"].max() * 1.1)
    ax.set_ylim(-0.6, len(s) - 0.1)
    ax.xaxis.set_major_formatter(money_m)
    ax.set_xlabel(f"{fy} drink revenue (USD); axis starts at $40M")
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=TOTAL), plt.Rectangle((0, 0), 1, 1, color=UP)],
              ["Core scenarios", f"Base + adding venues in Jan {fy}"], loc="upper center",
              bbox_to_anchor=(0.5, -0.2), ncol=2)
    clean_axis(ax, "x")
    by = s.set_index("Scenario")
    base = by.loc["Base"]
    outlook = {"Stable": "flat", "Declining": "lower", "Growing": "higher"}[base["Direction"]]
    whatif = by[by["Scenario Group"] != "Core"]["Forecast Drink Revenue"]
    return finish(fig, "15_scenarios_next_year.png",
                  f"{fy} looks {outlook} at {money(base['Forecast Drink Revenue'])} in the base case; "
                  f"adding venues lifts it to as much as {money(whatif.max())}",
                  f"{fy} drink revenue under each scenario, with the change vs the {cy} estimate (actual Jan to "
                  f"{CTX['latest']:%b} + forecast).\nBear: {by.loc['Bear', 'Assumptions']}. "
                  f"Bull: {by.loc['Bull', 'Assumptions']}.",
                  "Axis starts at $40M. A new venue is valued at RCI's typical first-year (opened) or established-venue "
                  "(acquired) drink revenue for its type.")


def forecast_by_type():
    t = load("p4_forecast_next_year_by_type.csv").set_index("Venue Type").loc[TYPE_ORDER[::-1]]
    fy, cy = CTX["fy"], CTX["cy"]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.barh(t.index, t["Next-Year Forecast"], color=[TYPE_COLORS[v] for v in t.index], height=0.6)
    ax.scatter(t["Current-Year Estimate"], range(len(t)), marker="|", s=500, color=INK, linewidths=2, zorder=3,
               label=f"{cy} estimate")
    for yv, (v, lab) in enumerate(zip(t["Next-Year Forecast"], t["Change Label"])):
        ax.text(max(v, t["Current-Year Estimate"].iloc[yv]) + 3e5, yv, f"{money(v)}  ·  {lab} vs {cy}", va="center",
                fontsize=9.5, color=INK)
    ax.set_xlim(0, t["Next-Year Forecast"].max() * 1.45)
    ax.xaxis.set_major_formatter(money_m)
    ax.set_xlabel(f"{fy} base-forecast drink revenue (USD)")
    ax.legend(loc="lower right", markerscale=0.5)
    clean_axis(ax, "x")
    within = (t["Change %"].abs() <= 0.05).all()
    nxt = CTX["latest"] + pd.DateOffset(months=1)
    return finish(fig, "16_forecast_next_year_by_venue_type.png",
                  f"Every venue type is forecast within 5% of its {cy} level in {fy}" if within
                  else f"{fy} base forecast by venue type",
                  f"{fy} base-forecast drink revenue by venue type (bars) vs the {cy} estimate (black tick: actual Jan "
                  f"to {CTX['latest']:%b} + forecast {nxt:%b} to Dec).")


# ---------------------------------------------------------------- README images
def readme_images() -> None:
    """Copy the key charts to images/ and write a one-line description of each for the README."""
    k = load("p1_kpis.csv").set_index("KPI")["Display Text"]
    fy, cy, y1 = CTX["fy"], CTX["cy"], CTX["last_full"]
    wf = load("p1_growth_bridge_waterfall.csv")
    w = wf[wf["Is Long Run"] & (wf["Detail"] == "By component")].set_index("Step")["Change Label"]
    t = wf[wf["Is Latest"] & (wf["Detail"] == "By component")].set_index("Step")["Change Label"]
    c = load(f"p3_type_growth_sources_since_{BASE_YEAR}.csv").groupby("Venue Type")["Change"].sum()
    gc, lat, sb = c["Gentlemen's club"], c["Latin-themed club"], c["Sports-bar restaurant"]
    rb = load("p3_type_revenue_by_basis.csv")
    est = rb[rb["Revenue Basis"] == "Est. total revenue"].set_index("Venue Type")["Avg Monthly Revenue per Venue"]
    a = load("p3_acquisitions.csv").dropna(subset=["Uplift %"]).sort_values("Uplift %")
    s = load("p4_scenario_summary.csv").set_index("Scenario")
    fa = load("p4_forecast_accuracy.csv")
    base_err = fa.loc[fa["Is Baseline"], "Venue Error Label"].iat[0]
    fa = fa.set_index("Model Role")
    picks = {
        "01_group_revenue_trend_and_forecast.png":
            f"Monthly group drink revenue 2015 to {CTX['latest']:%b %Y} with the forecast to Dec {fy}: last 12 months "
            f"{k['Drink revenue, last 12 months']} ({k['Growth vs prior 12 months']}), {fy} base forecast "
            f"{k['Next-year forecast (base)']} (80% range {k['Next-year forecast low (80%)']}–{k['Next-year forecast high (80%)']}).",
        f"02_growth_sources_since_{BASE_YEAR}.png":
            f"Waterfall from {w[str(BASE_YEAR)]} ({BASE_YEAR}) to {w[str(y1)]} ({y1}): acquisitions {w['Acquired venues']}, "
            f"new venues {w['New venues (opened / other)']}, same-venue {w['Same-venue growth']}, closures {w['Closed venues']}.",
        "03_last_12_months_bridge.png":
            f"Waterfall of the last 12 months vs the 12 before ({t['Prior 12 months']} to {t['Last 12 months']}): "
            f"same-venue {t['Same-venue growth']}, new venues {t['New venues (opened / other)']}, closures {t['Closed venues']}.",
        f"04_change_by_venue_type_since_{BASE_YEAR}.png":
            f"Change {BASE_YEAR} to {y1} by venue type and source: gentlemen's clubs {money(gc, True)}, "
            f"Latin clubs {money(lat, True)}, sports bars {money(sb, True)} "
            f"{'despite' if sb < 0 else 'including'} new openings.",
        "07_revenue_per_venue_by_type.png":
            f"Average monthly revenue per venue by type, drink sales vs estimated total revenue: on the estimate a "
            f"{IN_SENTENCE[est.idxmax()]} earns the most ({money(est.max())} a month).",
        "08_venue_growth_last_12_months.png":
            f"Diverging bars of each active venue's change vs a year ago: {k['Venues down more than 5%']} venues down "
            f"more than 5% ({k['Venues below last year']} below last year).",
        "11_acquisitions_before_vs_after.png":
            f"Average monthly drink sales 12 months before vs after each going-concern acquisition: "
            f"{'all' if (a['Uplift %'] > 0).all() else str(int((a['Uplift %'] > 0).sum())) + ' of ' + str(len(a))} rose "
            f"({a['Uplift Label'].iloc[0]} to {a['Uplift Label'].iloc[-1]}, {len(a)} deals).",
        "14_forecast_accuracy_vs_baseline.png":
            f"Back-tested venue-level forecast error by model: {MODEL_SHORT[CTX['model']]} "
            f"{fa.loc['Selected', 'Venue Error Label']} vs 'same month last year' baseline "
            f"{base_err} ({MODEL_SHORT[CTX['model']]}'s average 12-month group error "
            f"{fa.loc['Selected', 'Abs Error Label']}).",
        "15_scenarios_next_year.png":
            f"{fy} drink revenue by scenario vs the {cy} estimate {k['Current-year estimate']}: bear "
            f"{money(s.loc['Bear', 'Forecast Drink Revenue'])}, base {money(s.loc['Base', 'Forecast Drink Revenue'])}, "
            f"bull {money(s.loc['Bull', 'Forecast Drink Revenue'])}; adding venues lifts it to up to "
            f"{money(s['Forecast Drink Revenue'].max())}.",
    }
    IMAGES.mkdir(parents=True, exist_ok=True)
    for old in IMAGES.glob("*.png"):
        old.unlink()
    for name in picks:
        shutil.copy2(VISUALS / name, IMAGES / name)
    (IMAGES / "_list.txt").write_text("".join(f"{n} — {d}\n" for n, d in picks.items()), encoding="utf-8")
    print(f"  images/: {len(picks)} charts + _list.txt")


def main():
    VISUALS.mkdir(parents=True, exist_ok=True)
    for old in VISUALS.glob("*.png"):
        old.unlink()
    trend = load("p1_group_trend_and_forecast.csv", parse_dates=["Month"])
    actual = trend.loc[trend["Series"] == "Actual", "Month"]
    latest = actual.max()
    fy = int(load("p4_scenario_summary.csv")["Forecast Year"].iat[0])
    CTX.update(latest=latest, fy=fy, cy=fy - 1, model=SELECTED_MODEL.read_text().strip(),
               last_full=latest.year if latest.month == 12 else latest.year - 1,
               ttm_span=f"{latest - pd.DateOffset(months=11):%b %Y} to {latest:%b %Y}",
               source=(f"Source: Texas Comptroller Mixed Beverage Gross Receipts, RCI Hospitality's Texas venues, "
                       f"{actual.min():%b %Y} to {latest:%b %Y}. Drink sales only (liquor, wine, beer): door, dance "
                       f"and food revenue are not in the data."))
    for fn in (group_trend, growth_sources, ttm_bridge, type_contribution, revenue_by_type, type_share,
               revenue_per_venue, venue_yoy, top_venues, ramp, acquisitions, seasonality, drinks_mix,
               forecast_accuracy, scenarios, forecast_by_type):
        fn()
    readme_images()


if __name__ == "__main__":
    main()
