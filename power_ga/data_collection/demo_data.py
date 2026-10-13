"""生成可复现的教学用 8760 小时负荷、风电和光伏曲线。不是实测数据。"""

import csv
import math
from pathlib import Path


def main():
    """按确定性年季节、昼夜和短周期波动生成完整8760点教学曲线。"""
    path = Path(__file__).resolve().parents[2] / "input" / "hourly_profiles.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["hour", "load_mw", "wind_cf", "solar_cf"])
        for index in range(8760):
            day, hour = divmod(index, 24)
            # 合成负荷=80MW基荷+年周期15MW+日周期14MW+工作日4MW。
            season = math.sin(2 * math.pi * (day - 180) / 365)
            evening = (1 + math.sin(2 * math.pi * (hour - 14) / 24)) / 2
            weekday = 4 if day % 7 < 5 else 0
            load = 80 + 15 * season + 14 * evening + weekday
            wind = 0.38 + 0.16 * math.sin(2 * math.pi * day / 15) + \
                   0.10 * math.sin(2 * math.pi * hour / 24) + \
                   0.04 * math.sin(2 * math.pi * day / 41)
            wind = max(0.05, min(0.85, wind))
            # 光伏夜间归零，日内正弦峰值受年周期调制；cf始终在[0,1]。
            solar = max(0, math.sin(math.pi * (hour - 6) / 12)) * \
                    (0.70 + 0.20 * math.sin(2 * math.pi * day / 365))
            writer.writerow([index, f"{load:.6f}", f"{wind:.6f}", f"{solar:.6f}"])
    print(f"已生成演示数据: {path}")


if __name__ == "__main__":
    main()
