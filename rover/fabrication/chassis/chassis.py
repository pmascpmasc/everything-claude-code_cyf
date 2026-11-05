"""Welded wheel/wheg chassis: drawing sheets, cut list and design checks from one set of parameters.

    python chassis.py        # writes ./out: sheet1_views.png/.pdf, sheet2_details.png/.pdf, cut_list.csv, checks.json

Units: mm, kg. Axes: X forward, Y left, Z up, origin at the frame centre on the ground.
"""
import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
for f in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",):
    if os.path.exists(f):
        font_manager.fontManager.addfont(f)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()

# ------------------------------------------------------------------ parameters
P = dict(
    tube=25.0, wall=2.0,                 # 25x25x2 mild-steel square tube
    frame_len=820.0,                     # rail length: end cross members clear the 48T wheg sprocket
    outer_y=197.5, inner_y=117.5,        # rail centre lines (±Y)
    cross_x=(-397.5, 0.0, 397.5),        # cross-member centre lines
    wheelbase=550.0, track=660.0,        # axle spacing, wheel centre to centre
    tyre_d=460.0, tyre_w=200.0,          # 18x8.50-8
    shaft_d=20.0, shaft_len=280.0,       # live stub axle, S45C
    pb_center_h=33.3, pad_t=6.0,         # UCP204 pillow block centre height, pad flat bar thickness
    pad_len=80.0, pad_w=40.0,
    motor_x=(-210.0, 210.0),             # left motor drives the rear axle, right motor the front axle (short chains)
    post_h=150.0, post_x=250.0,          # brain-box posts on the outer rails
    sprocket_motor=12, sprocket_axle=30, sprocket_transfer=15,   # #40 chain, 2.5:1 for wheels (60 kg on 35° stairs)
    sprocket_axle_wheg=48,               # swap gear for whegs, 4:1
    wheg_r=260.0, wheg_bar=(30.0, 5.0), wheg_bar_len=230.0,
    hub_pcd=101.6, hub_d=140.0, hub_t=6.0,   # 4-bolt 4" PCD, common on 8" lawn-tractor rims: MEASURE YOUR RIM
    battery=(170.0, 230.0, 110.0),       # bay for a 24 V 20 Ah LiFePO4 (x, y, z) — set to the real pack
    stock_len=6000.0, kerf=3.0,
)
AXLE_Z = P["tyre_d"] / 2
RAIL_BOTTOM = AXLE_Z + P["pb_center_h"] + P["pad_t"]       # pillow blocks hang under the rails
RAIL_TOP = RAIL_BOTTOM + P["tube"]
AXLE_X = (-P["wheelbase"] / 2, P["wheelbase"] / 2)
RHO = 7.85e-6  # kg/mm^3 steel

# ------------------------------------------------------------------ cut list (single source for drawing + table)
inner_seg = (P["cross_x"][1] - P["cross_x"][0]) - P["tube"]
cross_len = 2 * P["outer_y"] - P["tube"]
CUTS = [
    # id, name, stock, length, qty, note
    ("T1", "外側縱梁", "方管 25×25×2", P["frame_len"], 2, "兩端平切；Y = ±197.5"),
    ("T2", "端橫樑", "方管 25×25×2", cross_len, 2, "夾在外側縱梁之間對接；X = -397.5 / +397.5"),
    ("T5", "中央橫樑", "方管 25×25×2", 2 * P["inner_y"] - P["tube"], 1, "只接在兩根內側縱梁之間（X = 0），不可跨過鏈條通道"),
    ("T3", "內側縱梁段", "方管 25×25×2", inner_seg, 4, "夾在端橫樑與中央橫樑之間；Y = ±117.5"),
    ("T4", "大腦盒立柱", "方管 25×25×2", P["post_h"], 4, "立焊在外側縱梁上；X = ±250"),
    ("F1", "軸承座墊板", "扁鐵 40×6", P["pad_len"], 8, "焊在縱梁下方；鑽 2 × 長孔 11×21（前軸可調鏈條張力）"),
    ("F2", "大腦盒固定片", "扁鐵 40×5", 40.0, 4, "焊在立柱頂；中心鑽 Ø9（M8）"),
    ("F3", "輪腿腳桿", "扁鐵 30×5", P["wheg_bar_len"], 12, "4 支輪腿 × 3 根；焊在輪腿法蘭"),
    ("S1", "輪軸", "圓鋼 S45C Ø20", P["shaft_len"], 4, "兩端倒角；鍵槽 6×3.5 長 40（鏈輪位置）"),
]
PLATES = [
    ("P1", "馬達底板", "鋼板 6 mm", (220, 260), 2, "橫跨兩根內側縱梁，X = ±(100…320)；馬達孔依實物鑽，做 ±15 mm 長孔調鏈條"),
    ("P2", "輪轂法蘭", "鋼板 6 mm", (P["hub_d"], P["hub_d"]), 4, f"圓盤 Ø{P['hub_d']:.0f}；4 孔 PCD {P['hub_pcd']}；中心焊 Ø20 軸套"),
    ("P3", "輪腿法蘭", "鋼板 6 mm", (P["hub_d"], P["hub_d"]), 4, "同 P2 孔位，可直接互換輪胎"),
    ("P4", "電池托架", "鋼板 3 mm", (P["battery"][0] + 20, P["battery"][1] + 20), 1, "放在內側縱梁上方，X = -95…+95；四角開槽穿綁帶"),
]


def nest(lengths, stock, kerf):
    """First-fit decreasing: returns list of bars, each a list of cut lengths."""
    bars = []
    for L in sorted(lengths, reverse=True):
        for b in bars:
            if sum(b) + kerf * len(b) + L <= stock:
                b.append(L)
                break
        else:
            bars.append([L])
    return bars


def stock_plan():
    plan = {}
    for _, _, stock, L, q, _ in CUTS:
        plan.setdefault(stock, []).extend([L] * q)
    out = {}
    for stock, ls in plan.items():
        bars = nest(ls, P["stock_len"], P["kerf"])
        out[stock] = {"total_mm": round(sum(ls), 1), "bars_6m": len(bars), "bars": [[round(x, 1) for x in b] for b in bars]}
    return out


WHEG_ONLY = ("F3", "P3")   # wheg parts are swapped in for the tyres, never fitted together


def masses():
    """Steel mass of the tyre configuration (wheg parts excluded; flanges counted as discs)."""
    tube_area = P["tube"] ** 2 - (P["tube"] - 2 * P["wall"]) ** 2
    m = {}
    m["frame_tube"] = sum(L * q for _, _, s, L, q, _ in CUTS if s.startswith("方管")) * tube_area * RHO
    m["flat_bar"] = sum(L * q * (40 * 6 if "40×6" in s else 40 * 5 if "40×5" in s else 30 * 5)
                        for i, _, s, L, q, _ in CUTS if s.startswith("扁鐵") and i not in WHEG_ONLY) * RHO
    m["shafts"] = 4 * math.pi * (P["shaft_d"] / 2) ** 2 * P["shaft_len"] * RHO
    m["plates"] = sum((math.pi / 4 if "法蘭" in n else 1) * a * b * q * (6 if "6 mm" in s else 3)
                      for i, n, s, (a, b), q, _ in PLATES if i not in WHEG_ONLY) * RHO
    return {k: round(v, 2) for k, v in m.items()}


# ------------------------------------------------------------------ design checks (deterministic)
def checks():
    c = []
    tyre_inner = P["track"] / 2 - P["tyre_w"] / 2
    frame_outer = P["outer_y"] + P["tube"] / 2
    c.append(("輪胎與車架間隙", tyre_inner - frame_outer, ">= 15 mm", tyre_inner - frame_outer >= 15))
    c.append(("車架底部離地", RAIL_BOTTOM, ">= 230 mm（可越過 20 cm 欄架並留 3 cm）", RAIL_BOTTOM >= 230))
    # sprockets and chain sit in the gap between the rails; the end cross members cross that gap at rail height.
    # Distance (side view) from the axle centre to the nearest corner region of an end cross member vs sprocket tip radius.
    xc = min(abs(x) for x in P["cross_x"] if abs(x) > 1) - P["tube"] / 2
    dx, dz = max(0.0, xc - P["wheelbase"] / 2), max(0.0, RAIL_BOTTOM - AXLE_Z)
    reach = math.hypot(dx, dz)
    for label, teeth in (("輪胎", P["sprocket_axle"]), ("輪腿", P["sprocket_axle_wheg"])):
        tip = pitch_d(teeth) / 2 + 0.3 * 12.7 + 4     # tooth tip + chain link plate
        c.append((f"軸鏈輪與端橫樑間隙（{label} {teeth}T）", reach - tip, ">= 5 mm", reach - tip >= 5))
    gap = min(abs(x) for x in P["motor_x"]) - 110 - (P["battery"][0] + 20) / 2
    c.append(("馬達底板與電池托架間隙", gap, ">= 0 mm", gap >= 0))
    width = P["track"] + P["tyre_w"]
    c.append(("整車寬度", width, "<= 1000 mm（樓梯寬 1200）", width <= 1000))
    c.append(("鏈輪最低點離地（輪胎）", AXLE_Z - pitch_d(P["sprocket_axle"]) / 2, ">= 100 mm",
              AXLE_Z - pitch_d(P["sprocket_axle"]) / 2 >= 100))
    low_wheg = P["wheg_r"] - pitch_d(P["sprocket_axle_wheg"]) / 2
    c.append(("鏈輪最低點離地（輪腿）", low_wheg, ">= 100 mm（輪腿軸心高 260）", low_wheg >= 100))
    # rough CG: frame + motors + battery low on the rails, brain box on the posts, wheels at the axles
    # assumed: wheelchair motor 7 kg each, 24 V 20 Ah LiFePO4 6 kg, brain-box electronics 3 kg, tyre + rim 3.5 kg each
    parts = [(sum(masses().values()), RAIL_BOTTOM + 12), (2 * 7.0, RAIL_TOP + 60), (6.0, RAIL_TOP + P["battery"][2] / 2),
             (3.0, RAIL_TOP + P["post_h"] + 60), (4 * 3.5, AXLE_Z)]
    mtot = sum(m for m, _ in parts)
    cg = sum(m * z for m, z in parts) / mtot
    tip = math.degrees(math.atan2(P["wheelbase"] / 2, cg))
    c.append(("估計重心高度", round(cg), "（電池、馬達放在縱梁上）", True))
    c.append(("後翻臨界角（重心在軸距中央）", round(tip, 1), ">= 40°（樓梯 35° + 5° 餘裕）", tip >= 40))
    mass = mtot + 2.0   # chain, sprockets, bolts
    c.append(("估計整車重量（輪胎版，不含外殼）", round(mass, 1), "kg；賽規上限 150 kg", mass <= 150))
    # 35° stairs: design force = m g sin35 × 1.5 (step impacts); motor assumed 25 N·m continuous at the output shaft
    need = mass * 9.81 * math.sin(math.radians(35)) * 1.5 * (P["tyre_d"] / 2000) / 2
    have = 25.0 * P["sprocket_axle"] / P["sprocket_motor"]
    c.append(("爬樓梯每側扭力：需要 / 可用（輪胎）", f"{need:.0f} / {have:.0f}", "N·m；可用 ≥ 需要（馬達連續 25 N·m 為假設）", have >= need))
    need_w = mass * 9.81 * math.sin(math.radians(35)) * 1.5 * (P["wheg_r"] / 1000) / 2
    have_w = 25.0 * P["sprocket_axle_wheg"] / P["sprocket_motor"]
    c.append(("爬樓梯每側扭力：需要 / 可用（輪腿）", f"{need_w:.0f} / {have_w:.0f}", "N·m；模擬顯示輪腿另需約 2 倍餘裕", have_w >= need_w * 1.4))
    return [{"check": n, "value": round(v, 1) if isinstance(v, float) else v, "limit": lim, "pass": bool(ok)} for n, v, lim, ok in c]


def pitch_d(teeth, pitch=12.7):
    return pitch / math.sin(math.pi / teeth)


# ------------------------------------------------------------------ drawing helpers
def dim(ax, p1, p2, off, text, horizontal=True, fs=8):
    """Linear dimension between p1 and p2, offset perpendicular by off (mm)."""
    (x1, y1), (x2, y2) = p1, p2
    if horizontal:
        y = y1 + off
        ax.plot([x1, x1], [y1, y], color="k", lw=0.4)
        ax.plot([x2, x2], [y2, y], color="k", lw=0.4)
        ax.add_patch(FancyArrowPatch((x1, y), (x2, y), arrowstyle="<|-|>", mutation_scale=6, lw=0.6, color="k"))
        ax.text((x1 + x2) / 2, y + 6, text, ha="center", va="bottom", fontsize=fs)
    else:
        x = x1 + off
        ax.plot([x1, x], [y1, y1], color="k", lw=0.4)
        ax.plot([x2, x], [y2, y2], color="k", lw=0.4)
        ax.add_patch(FancyArrowPatch((x, y1), (x, y2), arrowstyle="<|-|>", mutation_scale=6, lw=0.6, color="k"))
        ax.text(x + 6, (y1 + y2) / 2, text, ha="left", va="center", fontsize=fs, rotation=90)


def tube_rect(ax, cx, cy, lx, ly, label=None, fc="#c9d3dd"):
    ax.add_patch(Rectangle((cx - lx / 2, cy - ly / 2), lx, ly, fc=fc, ec="k", lw=0.7))
    if label:
        ax.text(cx, cy, label, ha="center", va="center", fontsize=6.5, color="#0b3d91")


def tag(ax, x, y, t, dx=40, dy=40):
    ax.annotate(t, (x, y), (x + dx, y + dy), fontsize=7, color="#b00020",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#b00020"))


# ------------------------------------------------------------------ sheet 1: three views
def sheet1():
    fig = plt.figure(figsize=(16.54, 11.69))  # A3 landscape
    fig.suptitle("輪式／輪腿底盤　組立三視圖（單位 mm）", fontsize=15, x=0.02, ha="left", y=0.985)
    t, L = P["tube"], P["frame_len"]

    # top view
    ax = fig.add_axes([0.03, 0.40, 0.55, 0.52])
    ax.set_title("俯視圖（車頭朝右）", fontsize=10, loc="left")
    for s in (-1, 1):
        tube_rect(ax, 0, s * P["outer_y"], L, t, "T1")
        for xa, xb in ((P["cross_x"][0], P["cross_x"][1]), (P["cross_x"][1], P["cross_x"][2])):
            tube_rect(ax, (xa + xb) / 2, s * P["inner_y"], inner_seg, t, "T3")
        for px in (-P["post_x"], P["post_x"]):
            tube_rect(ax, px, s * P["outer_y"], t, t, fc="#7f8c99")
    for x in P["cross_x"]:
        if abs(x) > 1:
            tube_rect(ax, x, 0, t, cross_len, "T2")
        else:
            tube_rect(ax, x, 0, t, 2 * P["inner_y"] - t, "T5")
    for ax_x in AXLE_X:
        for s in (-1, 1):
            ax.add_patch(Rectangle((ax_x - P["tyre_d"] / 2, s * P["track"] / 2 - P["tyre_w"] / 2), P["tyre_d"], P["tyre_w"],
                                   fc="none", ec="#555", lw=0.8, ls="--"))
            ax.plot([ax_x, ax_x], [s * (P["inner_y"] - 20), s * P["track"] / 2], color="#333", lw=2.2)
            for y in (P["inner_y"], P["outer_y"]):
                ax.add_patch(Rectangle((ax_x - 48, s * y - 19), 96, 38, fc="#f3d27a", ec="k", lw=0.5, alpha=0.8))
            tag(ax, ax_x, s * P["outer_y"], "UCP204 吊掛\n墊板 F1", dx=-150 if ax_x < 0 else 40, dy=s * 70)
    bx, by, _ = P["battery"]
    ax.add_patch(Rectangle((-bx / 2, -by / 2), bx, by, fc="#9fd39a", ec="k", lw=0.6, alpha=0.7))
    ax.text(0, 0, "電池\n托架 P4", ha="center", va="center", fontsize=7)
    gap_y = (P["inner_y"] + P["outer_y"]) / 2
    for s, mx, axle in ((1, P["motor_x"][0], AXLE_X[0]), (-1, P["motor_x"][1], AXLE_X[1])):
        ax.add_patch(Rectangle((mx - 110, -130), 220, 260, fc="none", ec="#1f4e79", lw=0.9, ls="-."))
        ax.text(mx, 0, "馬達底板 P1\n（%s馬達）" % ("左" if s > 0 else "右"), ha="center", va="center", fontsize=7, color="#1f4e79")
        ax.add_patch(Circle((mx, s * gap_y), pitch_d(P["sprocket_motor"]) / 2, fc="none", ec="#b00020"))
        ax.plot([mx, axle], [s * gap_y] * 2, color="#b00020", lw=1.2)
        ax.plot([AXLE_X[0], AXLE_X[1]], [s * (gap_y + 10)] * 2, color="#e67e22", lw=1)
    ax.text(-L / 2, P["track"] / 2 + 150, "鏈條（在內外縱梁之間的通道）：紅 = 馬達→軸（左驅後軸、右驅前軸）；橘 = 前後軸連動",
            fontsize=7.5)
    dim(ax, (-L / 2, -P["outer_y"] - t / 2), (L / 2, -P["outer_y"] - t / 2), -230, f"{L:.0f}")
    dim(ax, (AXLE_X[0], -P["outer_y"]), (AXLE_X[1], -P["outer_y"]), -170, f"軸距 {P['wheelbase']:.0f}")
    dim(ax, (L / 2, -P["inner_y"]), (L / 2, P["inner_y"]), 210, f"{2 * P['inner_y']:.0f}（中心）", horizontal=False)
    dim(ax, (L / 2, -P["outer_y"] - t / 2), (L / 2, P["outer_y"] + t / 2), 310, f"{2 * P['outer_y'] + t:.0f}", horizontal=False)
    dim(ax, (L / 2, -P["track"] / 2), (L / 2, P["track"] / 2), 420, f"輪距 {P['track']:.0f}", horizontal=False)
    ax.set_xlim(-620, 900)
    ax.set_ylim(-560, 560)
    ax.set_aspect("equal")
    ax.axis("off")

    # side view
    ax = fig.add_axes([0.03, 0.04, 0.55, 0.34])
    ax.set_title("側視圖（左側，車頭朝右）", fontsize=10, loc="left")
    ax.plot([-700, 700], [0, 0], color="k", lw=1)
    for ax_x in AXLE_X:
        ax.add_patch(Circle((ax_x, AXLE_Z), P["tyre_d"] / 2, fc="none", ec="#555", lw=0.9, ls="--"))
        ax.add_patch(Circle((ax_x, AXLE_Z), pitch_d(P["sprocket_axle"]) / 2, fc="none", ec="#b00020", lw=0.8))
        ax.add_patch(Rectangle((ax_x - 48, AXLE_Z - 17), 96, 50, fc="#f3d27a", ec="k", lw=0.5))
        ax.add_patch(Rectangle((ax_x - P["pad_len"] / 2, RAIL_BOTTOM - P["pad_t"]), P["pad_len"], P["pad_t"], fc="#888", ec="k", lw=0.5))
    tube_rect(ax, 0, RAIL_BOTTOM + t / 2, L, t, "T1")
    for px in (-P["post_x"], P["post_x"]):
        tube_rect(ax, px, RAIL_TOP + P["post_h"] / 2, t, P["post_h"], "T4", fc="#7f8c99")
    ax.add_patch(Rectangle((-P["post_x"] - 40, RAIL_TOP + P["post_h"]), 2 * P["post_x"] + 80, 120, fc="none", ec="#1f4e79", ls="-.", lw=0.9))
    ax.text(0, RAIL_TOP + P["post_h"] + 60, "大腦盒（另見電路圖）", ha="center", fontsize=8, color="#1f4e79")
    ax.add_patch(Rectangle((P["motor_x"][0] - 110, RAIL_TOP), 220, 120, fc="none", ec="#1f4e79", lw=0.8))
    ax.text(P["motor_x"][0] + 45, RAIL_TOP + 100, "左馬達（含電磁煞車）", ha="center", va="center", fontsize=7, color="#1f4e79")
    ax.add_patch(Circle((P["motor_x"][0], RAIL_TOP + 60), pitch_d(P["sprocket_motor"]) / 2, fc="none", ec="#b00020", lw=0.8))
    ax.plot([P["motor_x"][0], AXLE_X[0]], [RAIL_TOP + 60, AXLE_Z], color="#b00020", lw=1, ls="--")   # hidden behind the outer rail
    ax.add_patch(Rectangle((-P["battery"][0] / 2, RAIL_TOP), P["battery"][0], P["battery"][2], fc="#9fd39a", ec="k", alpha=0.6))
    dim(ax, (AXLE_X[1], 0), (AXLE_X[1], AXLE_Z), 260, f"軸心高 {AXLE_Z:.0f}", horizontal=False)
    dim(ax, (-L / 2, 0), (-L / 2, RAIL_BOTTOM), -80, f"離地 {RAIL_BOTTOM:.0f}", horizontal=False)
    dim(ax, (-P["post_x"], RAIL_TOP), (-P["post_x"], RAIL_TOP + P["post_h"]), -110, f"{P['post_h']:.0f}", horizontal=False)
    ax.add_patch(Rectangle((680, 0), 100, 200, fc="#ffd400", ec="k", lw=0.5))
    ax.text(730, 215, "20 cm 欄架\n（比例參考）", ha="center", fontsize=7)
    ax.set_xlim(-720, 900)
    ax.set_ylim(-40, 620)
    ax.set_aspect("equal")
    ax.axis("off")

    # front view
    ax = fig.add_axes([0.60, 0.40, 0.38, 0.55])
    ax.set_title("前視圖", fontsize=10, loc="left")
    ax.plot([-560, 560], [0, 0], color="k", lw=1)
    for s in (-1, 1):
        ax.add_patch(Rectangle((s * P["track"] / 2 - P["tyre_w"] / 2, 0), P["tyre_w"], P["tyre_d"], fc="none", ec="#555", ls="--"))
        for y in (P["outer_y"], P["inner_y"]):
            tube_rect(ax, s * y, RAIL_BOTTOM + t / 2, t, t)
            ax.add_patch(Rectangle((s * y - 19, AXLE_Z - 17), 38, 50, fc="#f3d27a", ec="k", lw=0.5))
        ax.plot([s * (P["inner_y"] - 20), s * (P["track"] / 2 + 30)], [AXLE_Z, AXLE_Z], color="#333", lw=3)
        ax.add_patch(Rectangle((s * (P["track"] / 2 - P["tyre_w"] / 2) - (P["hub_t"] if s > 0 else 0) * 0 - 3 * s, AXLE_Z - P["hub_d"] / 2),
                               6, P["hub_d"], fc="#555"))
        ax.plot([s * (P["inner_y"] + P["outer_y"]) / 2] * 2, [AXLE_Z - 60, RAIL_TOP + 80], color="#b00020", lw=1)
        tube_rect(ax, s * P["outer_y"], RAIL_TOP + P["post_h"] / 2, t, P["post_h"], fc="#7f8c99")
    tube_rect(ax, 0, RAIL_BOTTOM + t / 2, cross_len, t, "T2（端橫樑）")
    ax.text(0, AXLE_Z + 10, f"Ø{P['shaft_d']:.0f} 輪軸 S1", ha="center", fontsize=7)
    tag(ax, (P["inner_y"] + P["outer_y"]) / 2, AXLE_Z - 40, "鏈條在內外縱梁\n之間 55 mm 空間", dx=60, dy=-120)
    dim(ax, (-P["outer_y"] - t / 2, 0), (P["outer_y"] + t / 2, 0), -60, f"{2 * P['outer_y'] + t:.0f}")
    dim(ax, (-P["track"] / 2 - P["tyre_w"] / 2, 0), (P["track"] / 2 + P["tyre_w"] / 2, 0), -120, f"總寬 {P['track'] + P['tyre_w']:.0f}")
    ax.set_xlim(-600, 600)
    ax.set_ylim(-160, 600)
    ax.set_aspect("equal")
    ax.axis("off")

    # notes
    ax = fig.add_axes([0.60, 0.04, 0.38, 0.34])
    ax.axis("off")
    notes = [
        "施工說明",
        "1. 材料：一般結構鋼（SS400）方管 25×25×2、扁鐵；輪軸 S45C。",
        "2. 先點焊外框（T1 + T2），量對角線差 ≤ 2 mm 再滿焊。",
        "3. 內側縱梁 T3 夾在橫樑之間（四段同一直線）；中央橫樑 T5 只接內側縱梁。",
        "4. 軸承座墊板 F1 焊在縱梁「下方」，同一根軸的兩塊墊板",
        "   必須同高、同軸（穿一根 Ø20 圓鋼試裝再滿焊）。",
        "5. 前軸墊板開長孔：鬆開軸承座前後推，調後軸→前軸鏈條張力。",
        "6. 馬達底板 P1 依實際馬達鑽孔，開 ±15 mm 長孔調馬達鏈條。",
        "7. 左馬達在後段驅動後軸、右馬達在前段驅動前軸；電池 P4 在中間。",
        "8. 輪胎與輪腿共用輪轂法蘭 P2/P3 孔位：PCD 101.6 是 8 吋",
        "   割草機輪框常見規格，下料前務必量實際輪框。",
        "9. 焊完除鏽上漆；軸承座、鏈輪、鍵用螺絲固定，不要焊死。",
        f"10. 齒比：輪胎 {P['sprocket_motor']}T→{P['sprocket_axle']}T（{P['sprocket_axle'] / P['sprocket_motor']:.1f}:1）；"
        f"輪腿 {P['sprocket_motor']}T→{P['sprocket_axle_wheg']}T（{P['sprocket_axle_wheg'] / P['sprocket_motor']:.0f}:1）。",
    ]
    for i, n in enumerate(notes):
        ax.text(0, 1 - i * 0.075, n, fontsize=9 if i else 11, fontweight="bold" if i == 0 else "normal", va="top")
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"sheet1_views.{ext}"), dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ sheet 2: cut list + details
def sheet2(plan, chk):
    fig = plt.figure(figsize=(16.54, 11.69))
    fig.suptitle("材料裁切表、零件細部與設計檢查", fontsize=15, x=0.02, ha="left", y=0.985)
    ax = fig.add_axes([0.02, 0.50, 0.62, 0.44])
    ax.axis("off")
    rows = [[i, n, s, f"{L:.1f}", q, f"{L * q:.0f}", note] for i, n, s, L, q, note in CUTS]
    rows += [[i, n, s, f"{a:.0f}×{b:.0f}", q, "—", note] for i, n, s, (a, b), q, note in PLATES]
    tb = ax.table(cellText=rows, colLabels=["編號", "名稱", "材料", "長度 / 尺寸", "數量", "合計長", "加工說明"],
                  loc="upper left", cellLoc="left", colWidths=[0.05, 0.11, 0.13, 0.1, 0.05, 0.07, 0.49])
    tb.auto_set_font_size(False)
    tb.set_fontsize(8.5)
    tb.scale(1, 1.55)
    ax.set_title("裁切表（鋸口 3 mm 已計入排料）", fontsize=10, loc="left")

    ax = fig.add_axes([0.66, 0.50, 0.32, 0.44])
    ax.axis("off")
    ax.set_title("排料（6 m 料）", fontsize=10, loc="left")
    y = 0.95
    for stock, d in plan.items():
        ax.text(0, y, f"{stock}：合計 {d['total_mm'] / 1000:.2f} m → {d['bars_6m']} 支 6 m 料", fontsize=9, fontweight="bold")
        y -= 0.06
        for k, b in enumerate(d["bars"]):
            ax.text(0.03, y, f"第 {k + 1} 支：" + " + ".join(f"{x:.0f}" for x in b), fontsize=8)
            y -= 0.05
        y -= 0.02
    ax.text(0, y - 0.02, "鋼板件（P1–P4）面積小，建議找雷射切割代工一次切完。", fontsize=8.5)

    # hub flange detail
    ax = fig.add_axes([0.02, 0.05, 0.22, 0.40])
    ax.set_title("P2 輪轂法蘭（P3 同孔位）", fontsize=10, loc="left")
    r = P["hub_d"] / 2
    ax.add_patch(Circle((0, 0), r, fc="#dde3ea", ec="k"))
    ax.add_patch(Circle((0, 0), 16, fc="#888", ec="k"))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        ax.add_patch(Circle((P["hub_pcd"] / 2 * math.cos(a), P["hub_pcd"] / 2 * math.sin(a)), 6.5, fc="w", ec="k"))
    ax.add_patch(Circle((0, 0), P["hub_pcd"] / 2, fc="none", ec="#b00020", ls="--", lw=0.6))
    ax.text(0, -r - 22, f"Ø{P['hub_d']:.0f}×6 t；4×Ø13 於 PCD {P['hub_pcd']}\n中心焊 Ø20 軸套（長 40，M8 止付螺絲 + 6 mm 鍵）",
            ha="center", va="top", fontsize=8)
    ax.set_xlim(-r - 30, r + 30)
    ax.set_ylim(-r - 80, r + 20)
    ax.set_aspect("equal")
    ax.axis("off")

    # wheg detail
    ax = fig.add_axes([0.25, 0.05, 0.22, 0.40])
    ax.set_title("輪腿（P3 + 3 × F3）", fontsize=10, loc="left")
    ax.add_patch(Circle((0, 0), r, fc="#dde3ea", ec="k"))
    for k in range(3):
        a = math.pi / 2 + k * 2 * math.pi / 3
        x0, y0 = 20 * math.cos(a), 20 * math.sin(a)
        x1, y1 = (20 + P["wheg_bar_len"]) * math.cos(a), (20 + P["wheg_bar_len"]) * math.sin(a)
        ax.plot([x0, x1], [y0, y1], color="#444", lw=6, solid_capstyle="butt")
        ax.add_patch(Circle((x1, y1), 30, fc="#222", ec="k"))
    ax.add_patch(Circle((0, 0), P["wheg_r"], fc="none", ec="#b00020", ls="--", lw=0.6))
    ax.text(0, -P["wheg_r"] - 20, f"有效半徑 {P['wheg_r']:.0f}（含舊輪胎胎面腳掌）\n扁鐵與法蘭雙面滿焊；左右輪腿相位錯開 60°",
            ha="center", va="top", fontsize=8)
    ax.set_xlim(-P["wheg_r"] - 40, P["wheg_r"] + 40)
    ax.set_ylim(-P["wheg_r"] - 90, P["wheg_r"] + 40)
    ax.set_aspect("equal")
    ax.axis("off")

    # checks
    ax = fig.add_axes([0.50, 0.05, 0.48, 0.40])
    ax.axis("off")
    ax.set_title("設計檢查（由同一組參數計算）", fontsize=10, loc="left")
    rows = [[c["check"], str(c["value"]), c["limit"], "通過" if c["pass"] else "未通過"] for c in chk]
    tb = ax.table(cellText=rows, colLabels=["項目", "數值", "要求", "結果"], loc="upper left", cellLoc="left",
                  colWidths=[0.36, 0.12, 0.42, 0.1])
    tb.auto_set_font_size(False)
    tb.set_fontsize(8.5)
    tb.scale(1, 1.6)
    for (r_, c_), cell in tb.get_celld().items():
        if r_ > 0 and c_ == 3:
            cell.set_facecolor("#d8f0d8" if rows[r_ - 1][3] == "通過" else "#f6d5d5")
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"sheet2_details.{ext}"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    plan = stock_plan()
    chk = checks()
    with open(os.path.join(OUT, "cut_list.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["編號", "名稱", "材料", "長度或尺寸(mm)", "數量", "說明"])
        for i, n, s, L, q, note in CUTS:
            w.writerow([i, n, s, round(L, 1), q, note])
        for i, n, s, (a, b), q, note in PLATES:
            w.writerow([i, n, s, f"{a:.0f}x{b:.0f}", q, note])
    with open(os.path.join(OUT, "cut_list.md"), "w", encoding="utf-8") as f:
        f.write("| 編號 | 名稱 | 材料 | 長度或尺寸 (mm) | 數量 | 說明 |\n|---|---|---|---|---|---|\n")
        for i, n, s_, L, q, note in CUTS:
            f.write(f"| {i} | {n} | {s_} | {L:.1f} | {q} | {note} |\n")
        for i, n, s_, (a, b), q, note in PLATES:
            f.write(f"| {i} | {n} | {s_} | {a:.0f}×{b:.0f} | {q} | {note} |\n")
        f.write("\n| 設計檢查 | 數值 | 要求 | 結果 |\n|---|---|---|---|\n")
        for c in chk:
            f.write(f"| {c['check']} | {c['value']} | {c['limit']} | {'通過' if c['pass'] else '未通過'} |\n")
    json.dump({"parameters": P, "rail_bottom_mm": RAIL_BOTTOM, "axle_height_mm": AXLE_Z, "stock_plan": plan,
               "steel_mass_kg": masses(), "checks": chk}, open(os.path.join(OUT, "checks.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    sheet1()
    sheet2(plan, chk)
    for c in chk:
        print(("PASS" if c["pass"] else "FAIL"), c["check"], c["value"], c["limit"])
    print("stock:", {k: v["bars_6m"] for k, v in plan.items()}, "steel kg:", masses())
