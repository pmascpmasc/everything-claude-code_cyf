# 沙崙賽道 SimReady 場景

依 NVIDIA〈How to Use AI Agents to Prepare 3D Scenes for Simulation〉的流程，把賽道做成 Isaac Sim / Isaac Lab 可直接開啟的 OpenUSD 場景，並通過 SimReady 驗證。

交付檔：`out/course.usda`（Z 軸朝上、公尺、公斤）。

## 流程對照

| 文章步驟 | 這裡的做法 | 產出 |
|---|---|---|
| 0 定義目標 | 輸入是 `course_spec.json`（簡報 p.8–12 與瀏覽器模擬器的尺寸），輸出是 USD 場景，驗收標準是預覽檢查加 SimReady 驗證 | `course_spec.json` |
| 1 盤點場景（Blender MCP） | `check_scene.py` 盤點網格、材質、攝影機、燈光、剛體，列出缺少的語意標籤、碰撞體、物理材質 | `out/reports/inventory.json` |
| 2 以 USD 為交付標準 | `build_scene.py` 把每種障礙物做成獨立的 SimReady 資產，`course.usda` 用子圖層組合：geometry / physics / lighting / sensors | `out/assets/`、`out/layers/` |
| 3 語意標籤 | `UsdSemantics.LabelsAPI`：物件用 `class` 分類，材質用 `material` 分類 | 寫在 USD 內 |
| 4 物理感知材質 | 每種材質都有 UsdPreviewSurface 外觀加 `UsdPhysics.MaterialAPI`（摩擦、彈性、密度），泥水坑摩擦 0.15 與瀏覽器模擬器一致 | `out/material_metadata.json` |
| 5 先配置感測器 | 總覽攝影機，以及每關前 3 m、高 0.35 m 的機器人視角攝影機（FPV 安裝高度） | `out/layers/sensors.usda` |
| 6 物理就緒（ovphysx） | `check_scene.py`：碰撞體、質量、動態體不可用三角網格碰撞、懸空或下沉、動態體互相穿插，以及實測尺寸與規格比對 | `out/reports/physics_readiness.json` |
| 7 預覽渲染（ovrtx） | `preflight/render.mjs`：彩色與語意渲染，檢查目標可見度、標籤、材質、光照、遮擋、比例，並產生縮圖 | `out/reports/preflight_report.json`、`out/reports/preflight/*.png` |
| 8 SimReady 驗收 | 官方 `simready-validate`，Robotics-Prop 4.0.0 profile | `out/reports/simready_validation.{json,html}` |

障礙物資產：`hurdle_h05/h10/h15/h20`、`mud_pit`、`stairs_platform_ramp`（第 3、4 關）、`cone_barrier`（第 5 關，動態）、`traffic_cone`（動態）、`pitch_roll_ramps`、`gravel_pile`。賽道固定設施為運動學剛體（kinematic），錐筒路障是動態剛體，被撞會倒。

## 執行

需要 Python 3.11 或 3.12、Node.js 與 Playwright。

```bash
pip install usd-core simready-validate simready-foundation-tier-core simready-foundation-tier-sensors
cd rover/sim/scene
python build_scene.py                 # 產生 out/
python check_scene.py                 # 步驟 1、6
python preflight/export_preview.py
node preflight/render.mjs             # 步驟 7（從 cdn.jsdelivr.net 載入 three.js）
ls out/assets/*/simready_usd/sm_*.usda > assets.txt
simready-validate --asset_list assets.txt --profile Robotics-Prop --version 4.0.0 \
  --output out/reports/simready_validation.json --output-html out/reports/simready_validation.html
```

## 目前結果（2026-11-04）

- **物理就緒**：0 失敗、1 警告。交叉俯仰坡道內部最陡 17.9°（15° 俯仰加上側傾），入口淡入段 26.4°；入口形狀沿用原模型，等 12/4 正式規格再修。
- **預覽渲染**：11/11 通過。第一次跑時第 1、5 關的目標在機器人視角中太小，原因是攝影機擺太遠、太平；改成關前 3 m 並往下看後通過。
- **SimReady**：10 個資產都只剩 `SR.004` 一項失敗，原因是 `qcode`（Wikidata 物件編碼）空白。這個工作環境連不上 wikidata.org，我沒有憑記憶填編碼。補上方法：在各資產的 `sm_<name>.json` 填入 `qcode`，或開放網路後由程式查詢。

## 與文章的差異

- **沒有 Blender 來源檔**：賽道直接從規格以程式生成，所以不需要 Blender MCP 盤點；`check_scene.py` 盤點的是生成後的 USD。
- **沒有 NVIDIA GPU**：ovphysx 與 ovrtx 都無法執行。物理檢查改成靜態規則檢查，沒有實際跑 PhysX；預覽渲染改用 three.js，不是 RTX。所以 RTX 光照效果和 PhysX 碰撞行為都**沒有驗證**。第一次在 Isaac Sim 開啟時，要檢查車輛與錐筒的碰撞、泥水坑摩擦。
- **沒有多代理協作**：各步驟是可重跑的程式，判斷性的工作（語意分類、材質分類、修正攝影機）由我完成，判斷理由寫在程式註解裡。
- **整個場景沒有 SimReady 場景級 profile**：驗證是逐一資產跑 Robotics-Prop；組合後的場景由 `check_scene.py` 與預覽渲染把關。
