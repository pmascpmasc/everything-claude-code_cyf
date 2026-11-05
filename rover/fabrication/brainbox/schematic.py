"""Brain-box wiring: schematic (PNG/SVG/PDF) and wiring table (CSV) from one connection list.

    python schematic.py      # writes ./out

Safety chain: battery -> main fuse -> main switch -> [E-stop NC] -> [RC arm relay NO] -> contactor coil.
Losing either the E-stop or the RC link drops the contactor, cutting motor power; the wheelchair motors'
spring-applied brakes then lock because their release coils are fed from the switched (contactor) side.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()

# ------------------------------------------------------------------ connection list (also the wiring table)
# from, to, wire, colour, protected by, note
WIRES = [
    ("BAT+（電池，底盤上）", "F1 主保險絲 60 A", "8 AWG", "紅", "—", "F1 裝在電池端 15 cm 內"),
    ("F1", "J1 SB50 電池接頭（底盤↔大腦盒）", "8 AWG", "紅", "F1", "SB50 紅色外殼"),
    ("J1 BAT+", "SW1 主電源開關（100 A）", "8 AWG", "紅", "F1", "鑰匙或旋鈕式電池隔離開關"),
    ("SW1", "匯流排 VBAT_SW", "8 AWG", "紅", "F1", ""),
    ("VBAT_SW", "K1 主接觸器 觸點 A", "10 AWG", "紅", "F1", "K1：24 V 線圈、DC 100 A 常開"),
    ("K1 觸點 B", "匯流排 VMOT", "10 AWG", "紅", "F1", "急停或失聯時斷開"),
    ("VMOT", "F2 40 A → 馬達控制器 B+", "10 AWG", "紅", "F2", ""),
    ("馬達控制器 B-", "匯流排 GND", "10 AWG", "黑", "—", ""),
    ("VMOT", "F3 5 A → J4 煞車釋放 L+ / R+", "18 AWG", "紫", "F3", "煞車只在 K1 吸合時才放開"),
    ("VMOT", "F4 15 A → J5 擺臂控制器 B+", "14 AWG", "紅", "F4", "只有履帶底盤用"),
    ("馬達控制器 M1A / M1B", "J2 PP45 → 左馬達", "12 AWG", "黃 / 綠", "F2", "方向相反就對調兩線"),
    ("馬達控制器 M2A / M2B", "J3 PP45 → 右馬達", "12 AWG", "黃 / 綠", "F2", ""),
    ("VBAT_SW", "F5 2 A → S1 急停（常閉）", "20 AWG", "橙", "F5", "安全迴路起點"),
    ("S1 急停", "K2 失聯繼電器 COM→NO", "20 AWG", "橙", "F5", "S1：22 mm 紅色蘑菇頭，自鎖、旋轉復歸"),
    ("K2 NO", "K1 線圈 +（並聯 D1 1N5408、LED 綠「ARMED」）", "20 AWG", "橙", "F5", "D1 陰極接線圈 +"),
    ("K1 線圈 −", "GND", "20 AWG", "黑", "—", ""),
    ("VBAT_SW", "F6 5 A → U1 24→5 V 3 A、U2 24→12 V 2 A", "18 AWG", "紅", "F6", "不經 K1：急停後接收機與影像仍有電"),
    ("U1 5 V", "接收機 BAT、K2 RC 開關模組 5 V", "22 AWG", "紅", "F6", ""),
    ("U2 12 V", "FPV 攝影機 + 圖傳、狀態燈", "22 AWG", "紅", "F6", ""),
    ("接收機 CH2（油門）", "馬達控制器 S1", "26 AWG 杜邦", "白", "—", "控制器設 RC、混控（tank）模式"),
    ("接收機 CH1（轉向）", "馬達控制器 S2", "26 AWG 杜邦", "白", "—", ""),
    ("接收機 CH5（解鎖開關）", "K2 RC 開關模組 訊號", "26 AWG 杜邦", "白", "—", "接收機失控保護：CH5 = 關"),
    ("接收機 CH3", "擺臂控制器 S1", "26 AWG 杜邦", "白", "—", "只有履帶底盤用"),
    ("馬達控制器 0V", "接收機 GND", "26 AWG 杜邦", "黑", "—", "訊號共地；控制器的 5 V 輸出不要接（剪紅線）"),
]

BOM = [
    ("F1", "MIDI 保險絲 60 A + 座", 1), ("F2", "ANL/MIDI 保險絲 40 A + 座", 1), ("F3, F5, F6", "ATO 刀型保險絲 5 / 2 / 5 A + 座", 3),
    ("F4", "ATO 15 A（履帶擺臂）", 1), ("SW1", "電池隔離開關 100 A", 1), ("K1", "DC 主接觸器 24 V 線圈 100 A 常開", 1),
    ("K2", "RC 開關模組（PWM 轉繼電器，5 V，觸點 ≥ 2 A）", 1), ("S1", "急停蘑菇頭 22 mm 常閉、自鎖", 1), ("D1", "1N5408 二極體", 1),
    ("U1", "DC-DC 24→5 V 3 A", 1), ("U2", "DC-DC 24→12 V 2 A", 1), ("控制器", "雙通道 24 V ≥ 30 A，RC 輸入、訊號逾時停車（例：Sabertooth 2x32）", 1),
    ("J1", "Anderson SB50 紅", 1), ("J2, J3", "Anderson PP45 一對", 2), ("J4", "Anderson PP15 四極（煞車）", 1),
    ("線材", "矽膠線 8 / 10 / 12 / 18 / 20 / 22 AWG、壓接端子、熱縮套管", 1), ("盒體", "IP54 以上電氣盒 + 防水接頭 PG7/PG9", 1),
]


# ------------------------------------------------------------------ hand-placed ladder schematic
PWR, SAFE, SIG, LOGIC, K = "#222222", "#e67e22", "#1565c0", "#444444", "#b00020"


class Sheet:
    def __init__(self):
        self.fig, self.ax = plt.subplots(figsize=(16.54, 11.69))   # A3 landscape
        self.ax.set_xlim(-1, 27)
        self.ax.set_ylim(-13.2, 3.4)
        self.ax.set_aspect("equal")
        self.ax.axis("off")

    def wire(self, pts, c=PWR, lw=2.2, ls="-"):
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color=c, lw=lw, ls=ls, solid_capstyle="round", zorder=1)

    def text(self, x, y, t, fs=9, c="k", **kw):
        self.ax.text(x, y, t, fontsize=fs, color=c, zorder=5, **kw)

    def dot(self, x, y, c=PWR):
        self.ax.add_patch(Circle((x, y), 0.08, color=c, zorder=4))

    def fuse(self, x, y, label, c=PWR, lw=2.2):
        self.wire([(x, y), (x + 0.2, y)], c, lw)
        self.ax.add_patch(Rectangle((x + 0.2, y - 0.13), 0.6, 0.26, fc="white", ec=c, lw=1.4, zorder=3))
        self.wire([(x + 0.2, y), (x + 0.8, y)], c, 1.0)
        self.wire([(x + 0.8, y), (x + 1, y)], c, lw)
        self.text(x + 0.5, y + 0.25, label, 8.5, c, ha="center")

    def switch(self, x, y, label, c=PWR, lw=2.2, nc=False, button=False):
        self.wire([(x, y), (x + 0.25, y)], c, lw)
        self.wire([(x + 0.75, y), (x + 1, y)], c, lw)
        for cx in (x + 0.25, x + 0.75):
            self.ax.add_patch(Circle((cx, y), 0.06, fc="white", ec=c, lw=1.4, zorder=3))
        if nc:   # normally closed push button: bar bridges the contacts, stem above
            self.wire([(x + 0.2, y - 0.1), (x + 0.8, y - 0.1)], c, 1.6)
            self.wire([(x + 0.5, y - 0.1), (x + 0.5, y + 0.35)], c, 1.2)
            self.wire([(x + 0.35, y + 0.35), (x + 0.65, y + 0.35)], c, 1.6)
        else:
            self.wire([(x + 0.25, y), (x + 0.72, y + 0.28)], c, 1.6)
        self.text(x + 0.5, y + 0.45, label, 8.5, c, ha="center")

    def coil(self, x, y, label, c=K):
        """Vertical relay coil from (x, y) down to (x, y - 1.2)."""
        self.wire([(x, y), (x, y - 0.3)], SAFE, 1.6)
        self.ax.add_patch(Rectangle((x - 0.18, y - 0.9), 0.36, 0.6, fc="white", ec=c, lw=1.6, zorder=3))
        self.wire([(x, y - 0.9), (x, y - 1.2)], c, 1.6)
        self.text(x - 0.25, y - 0.6, label, 8.5, c, ha="right", va="center")

    def diode(self, x, y, label, c="k", led=False):
        """Vertical diode, cathode on top (reverse across the coil), from (x, y) to (x, y - 1.2)."""
        self.wire([(x, y), (x, y - 1.2)], c if not led else "#2e7d32", 1.2)
        col = "#2e7d32" if led else c
        if led:   # LED forward from top to bottom
            self.ax.add_patch(Polygon([(x - 0.17, y - 0.45), (x + 0.17, y - 0.45), (x, y - 0.75)], fc="white", ec=col, zorder=3))
            self.wire([(x - 0.17, y - 0.75), (x + 0.17, y - 0.75)], col, 1.4)
            for k in (0, 0.15):
                self.ax.annotate("", (x + 0.45, y - 0.45 - k), (x + 0.2, y - 0.6 - k), arrowprops=dict(arrowstyle="->", color=col, lw=0.8))
        else:
            self.ax.add_patch(Polygon([(x - 0.17, y - 0.75), (x + 0.17, y - 0.75), (x, y - 0.45)], fc="white", ec=col, zorder=3))
            self.wire([(x - 0.17, y - 0.45), (x + 0.17, y - 0.45)], col, 1.4)
        self.text(x + 0.25, y - 0.95, label, 8, col, ha="left")

    def ground(self, x, y, c=PWR):
        self.wire([(x, y), (x, y - 0.15)], c, 1.4)
        for i, w in enumerate((0.24, 0.16, 0.08)):
            self.wire([(x - w, y - 0.15 - i * 0.07), (x + w, y - 0.15 - i * 0.07)], c, 1.2)

    def box(self, x0, y0, x1, y1, title, c="k", fs=9):
        self.ax.add_patch(Rectangle((x0, y1), x1 - x0, y0 - y1, fc="#f6f8fb", ec=c, lw=1.4, zorder=2))
        self.text((x0 + x1) / 2, (y0 + y1) / 2, title, fs, c, ha="center", va="center")

    def pin(self, x, y, name, side):
        off = {"l": (0.08, 0, "left", "center"), "r": (-0.08, 0, "right", "center"),
               "t": (0, -0.12, "center", "top"), "b": (0, 0.12, "center", "bottom")}[side]
        self.text(x + off[0], y + off[1], name, 7.5, "#555", ha=off[2], va=off[3])

    def motor(self, x, y, label):
        self.ax.add_patch(Circle((x, y), 0.35, fc="white", ec=PWR, lw=1.6, zorder=3))
        self.text(x, y, "M", 11, PWR, ha="center", va="center")
        self.text(x + 0.5, y, label, 8.5, PWR, va="center")


def draw():
    S = Sheet()
    S.text(-0.8, 3.0, "大腦盒電路圖（24 V）", 17, weight="bold")
    S.text(-0.8, 2.4, "黑粗線 = 動力　橙 = 安全迴路（急停 / 失聯）　藍 = 遙控訊號　灰 = 控制電源", 10, "#555")

    # ---------------- row 1: power path y = 0
    S.box(-0.8, 0.9, 0.8, -0.9, "電池\n24 V LiFePO4\n20 Ah 含 BMS\n（在底盤上）", fs=8)
    S.wire([(0.8, 0.4), (1.2, 0.4), (1.2, 0)])
    S.wire([(0.8, -0.4), (1.2, -0.4), (1.2, -0.8)])
    S.ground(1.2, -0.8)
    S.fuse(1.2, 0, "F1 60 A")
    S.wire([(2.2, 0), (3.0, 0)])
    S.ax.add_patch(Rectangle((2.6, -0.2), 0.3, 0.4, fc="#e53935", ec="k", zorder=3))
    S.text(2.75, -0.45, "J1 SB50", 8, ha="center", va="top")
    S.switch(3.0, 0, "SW1 主開關")
    S.wire([(4.0, 0), (6.0, 0)])
    S.dot(5.0, 0)
    S.text(5.0, -0.3, "VBAT_SW", 8, ha="center", va="top")
    S.switch(6.0, 0, "K1 主接觸器觸點（常開）\n線圈在下方安全迴路", K)
    S.wire([(7.0, 0), (9.0, 0)])
    S.dot(8.0, 0)
    S.text(8.0, -0.3, "VMOT", 8, ha="center", va="top")
    S.fuse(9.0, 0, "F2 40 A")
    S.wire([(10.0, 0), (17.0, 0)])
    S.box(17.0, 1.2, 21.0, -1.8, "雙通道馬達控制器\n24 V ≥ 30 A\nRC 混控模式\n訊號逾時停車")
    S.pin(17.0, 0, "B+", "l")
    S.pin(17.0, -1.0, "B-", "l")
    S.wire([(17.0, -1.0), (16.4, -1.0), (16.4, -1.3)])
    S.ground(16.4, -1.3)
    for y, lab, nm in ((0.7, "左馬達（J2 PP45）", "M1"), (-0.6, "右馬達（J3 PP45）", "M2")):
        S.pin(21.0, y, nm, "r")
        S.wire([(21.0, y), (22.6, y)], PWR, 1.8)
        S.motor(23.0, y, lab)
    for x, nm in ((18.0, "0V"), (19.3, "S2"), (20.3, "S1")):
        S.pin(x, -1.8, nm, "b")
    S.wire([(18.0, -1.8), (18.0, -2.3)], SIG, 1.2)
    S.ground(18.0, -2.3, SIG)
    S.text(17.85, -2.95, "0V 與接收機 GND 共地", 7.5, SIG, ha="right")

    # VMOT branches (only live while K1 is closed)
    S.wire([(8.0, 0), (8.0, -2.6)])
    S.dot(8.0, -1.4)
    S.wire([(8.0, -1.4), (9.0, -1.4)], PWR, 1.6)
    S.fuse(9.0, -1.4, "F3 5 A", PWR, 1.6)
    S.wire([(10.0, -1.4), (11.0, -1.4)], PWR, 1.6)
    S.box(11.0, -1.0, 13.8, -1.8, "J4 煞車釋放線圈 ×2\n通電放開、斷電抱死", fs=8)
    S.wire([(13.8, -1.4), (14.3, -1.4), (14.3, -1.7)], PWR, 1.6)
    S.ground(14.3, -1.7)
    S.wire([(8.0, -2.6), (9.0, -2.6)], PWR, 1.6)
    S.fuse(9.0, -2.6, "F4 15 A", PWR, 1.6)
    S.wire([(10.0, -2.6), (11.0, -2.6)], PWR, 1.6)
    S.box(11.0, -2.3, 13.8, -2.9, "J5 擺臂控制器（履帶用）", fs=8)

    # ---------------- row 2: safety chain y = -4.4
    y = -4.4
    S.wire([(5.0, 0), (5.0, y)], SAFE, 1.6)
    S.dot(5.0, y, SAFE)
    S.wire([(5.0, y), (6.0, y)], SAFE, 1.6)
    S.fuse(6.0, y, "F5 2 A", SAFE, 1.6)
    S.wire([(7.0, y), (8.0, y)], SAFE, 1.6)
    S.switch(8.0, y, "S1 急停\n（常閉、自鎖）", SAFE, 1.6, nc=True)
    S.wire([(9.0, y), (10.6, y)], SAFE, 1.6)
    S.switch(10.6, y, "K2 失聯繼電器\n（常開）", SAFE, 1.6)
    S.wire([(11.6, y), (16.6, y)], SAFE, 1.6)
    for x in (13.4, 14.5, 16.6):
        S.dot(x, y, SAFE)
    S.coil(13.4, y, "K1\n線圈")
    S.ground(13.4, y - 1.2, K)
    S.diode(14.5, y, "D1 1N5408\n（續流）")
    S.ground(14.5, y - 1.2, "k")
    S.diode(16.6, y, "ARMED 綠燈\n（串 2.2 kΩ）", led=True)
    S.ground(16.6, y - 1.2, "#2e7d32")
    S.box(10.4, -5.2, 12.0, -6.0, "K2 RC 開關\n模組", c=SAFE, fs=8)
    S.wire([(11.1, -5.2), (11.1, y + 0.2)], SAFE, 1.0, "--")

    # ---------------- row 3: logic supply (not switched by K1) y = -8
    y3 = -8.0
    S.wire([(5.0, y), (5.0, y3)], LOGIC, 1.6)
    S.wire([(5.0, y3), (6.0, y3)], LOGIC, 1.6)
    S.fuse(6.0, y3, "F6 5 A", LOGIC, 1.6)
    S.wire([(7.0, y3), (8.4, y3)], LOGIC, 1.6)
    S.dot(7.6, y3, LOGIC)
    S.box(8.4, y3 + 0.4, 10.2, y3 - 0.4, "U1 DC-DC\n24→5 V 3 A", fs=8)
    S.wire([(10.2, y3), (16.0, y3)], LOGIC, 1.6)
    S.dot(11.6, y3, LOGIC)
    S.wire([(11.6, y3), (11.6, -6.0)], LOGIC, 1.2)
    S.text(11.7, -6.9, "5 V", 7.5, LOGIC)
    S.box(16.0, y3 + 0.8, 22.0, y3 - 1.0, "遙控接收機（≥ 6 通道）\n失控保護設定：CH5 = 關、油門置中", fs=9)
    S.pin(16.0, y3, "BAT", "l")
    S.wire([(19.0, y3 - 1.0), (19.0, y3 - 1.4)], SIG, 1.2)
    S.ground(19.0, y3 - 1.4, SIG)
    S.pin(19.0, y3 - 1.0, "GND", "b")
    for x, ch, to, lab in ((20.3, "CH2", 20.3, "油門"), (19.3, "CH1", 19.3, "轉向")):
        S.pin(x, y3 + 0.8, ch, "t")
        S.wire([(x, y3 + 0.8), (x, -1.8)], SIG, 1.2)
        S.text(x + 0.08, -5.6, lab, 7.5, SIG, rotation=90)
    S.pin(17.0, y3 + 0.8, "CH5", "t")
    S.wire([(17.0, y3 + 0.8), (17.0, -6.6), (11.2, -6.6), (11.2, -6.0)], SIG, 1.2)
    S.text(14.2, -6.55, "CH5 解鎖開關：開 = 吸合", 7.5, SIG, ha="center", va="bottom")
    S.pin(21.3, y3 + 0.8, "CH3", "t")
    S.wire([(21.3, y3 + 0.8), (21.3, -6.4), (22.6, -6.4)], SIG, 1.2)
    S.text(22.7, -6.4, "→ 擺臂控制器 S1（履帶用）", 7.5, SIG, va="center")
    S.wire([(7.6, y3), (7.6, y3 - 2.0), (8.4, y3 - 2.0)], LOGIC, 1.6)
    S.box(8.4, y3 - 1.6, 10.2, y3 - 2.4, "U2 DC-DC\n24→12 V 2 A", fs=8)
    S.wire([(10.2, y3 - 2.0), (11.0, y3 - 2.0)], LOGIC, 1.6)
    S.text(11.1, y3 - 2.0, "FPV 攝影機 + 圖傳、狀態燈", 8.5, LOGIC, va="center")

    # ---------------- notes
    notes = [
        "動作原理",
        "・急停 S1 按下 或 遙控失聯（接收機把 CH5 打到「關」）→ K2 或 S1 斷開 → K1 線圈失電 → 馬達與煞車斷電，煞車抱死。F1 裝在電池端 15 cm 內。",
        "・接收機與 FPV 從 VBAT_SW 取電，不經 K1：急停後仍看得到畫面、收得到訊號；要重新出發需旋開急停並把 CH5 撥回「開」。",
        "・控制器本身也設訊號逾時停車，是第二層保護。控制器的 5 V 輸出不要接到接收機（兩個電源會互衝），只共地。",
        "・煞車釋放由 K1 後端供電：車停在坡上但 K1 吸合時煞車是放開的，靠減速箱與控制器剎車；若控制器有煞車輸出功能，改接它更好（需查手冊）。",
    ]
    for i, n in enumerate(notes):
        S.text(-0.8, -10.9 - i * 0.48, n, 10 if i == 0 else 8.5, weight="bold" if i == 0 else "normal")
    for ext in ("png", "svg", "pdf"):
        S.fig.savefig(os.path.join(OUT, f"schematic.{ext}"), dpi=160 if ext == "png" else None, bbox_inches="tight")
    plt.close(S.fig)


if __name__ == "__main__":
    with open(os.path.join(OUT, "wiring_table.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["#", "從", "到", "線徑", "顏色", "保護", "說明"])
        for i, row in enumerate(WIRES, 1):
            w.writerow([i, *row])
    with open(os.path.join(OUT, "bom.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["代號", "品項", "數量"])
        w.writerows(BOM)
    with open(os.path.join(OUT, "wiring_table.md"), "w", encoding="utf-8") as f:
        f.write("| # | 從 | 到 | 線徑 | 顏色 | 保護 | 說明 |\n|---|---|---|---|---|---|---|\n")
        for i, row in enumerate(WIRES, 1):
            f.write("| " + " | ".join([str(i), *row]) + " |\n")
        f.write("\n| 代號 | 品項 | 數量 |\n|---|---|---|\n")
        for row in BOM:
            f.write("| " + " | ".join(map(str, row)) + " |\n")
    draw()
    print("wires:", len(WIRES), "bom:", len(BOM))
