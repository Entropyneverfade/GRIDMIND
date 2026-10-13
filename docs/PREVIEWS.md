# 交互窗口公开演示 / Public viewer demonstration

这些 PNG 来自**合成**八类机组全年运行结果，使用正式单文件 EXE 的 `--export-demo-views` 入口导出。该入口与可见窗口共用 `period_bounds()` 和 `draw_view()`；这些是程序导出的图，不是桌面窗口截图。The images are EXE exports from a fully synthetic 8,760-hour result, using the same range selection and drawing functions as the interactive desktop window. They are exported views, not screenshots of the window controls.

| 图片 / Image | 左闭右开小时区间 / `[start,end)` | 说明 / Meaning |
|---|---:|---|
| [第182日 / Day 182](../examples/previews/v0.2.0/day_182.png) | `[4344,4368)` | 24 hourly values; all eight types, charging below zero and PV curtailment hatch / 八类机组、负向充电与弃光斜线 |
| [第27周 / Week 27](../examples/previews/v0.2.0/week_27.png) | `[4368,4536)` | 168 hourly values / 168小时 |
| [第7月 / Month 7](../examples/previews/v0.2.0/month_7.png) | `[4344,5088)` | 744 hourly values / 744小时 |
| [全年 / Full year](../examples/previews/v0.2.0/year_1.png) | `[0,8760)` | All original hours without aggregation / 不降采样的全年总览 |
| [自定义 / Custom](../examples/previews/v0.2.0/custom_137_193.png) | `[137,193)` | Arbitrary 56-hour range / 任意56小时区间 |

**图例规则 / Legend rule:** Coal red, gas orange, biomass brown, hydro cyan, pumped storage dark blue, battery blue, PV yellow, wind green, load magenta. Normal wind/PV use solid color, while curtailed wind/PV use diagonal hatching of the same color. 储能充电画在零线下方；充放电库存数值可在逐时 CSV 中核对。月度未用水预算不等同逐时弃水功率，因此不伪造弃水色块。

## 从公开源码复现 / Reproduce from public source

```powershell
python -m pip install -r requirements.txt
python -m examples.synthetic_eight_type --output synthetic_demo
powershell -NoProfile -ExecutionPolicy Bypass -File gridmind_app/build.ps1
.\GRIDMIND.exe --export-demo-views synthetic_demo synthetic_views
.\GRIDMIND.exe --viewer synthetic_demo
```

源曲线由固定随机种子独立合成，没有从外部项目库采样。The synthetic result generator calls the actual chronological simulation and writes the standard hourly table. It verifies 8,760 hours and a near-zero hourly balance residual; the public gallery contains only synthetic PNGs.
