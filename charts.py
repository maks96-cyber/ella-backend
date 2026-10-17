"""Данные для графиков и разрезов в HUD (модули 9, 13, 16, 17).

Сервер считает цифры по тем же формулам, что и калькуляторы, а HUD
рисует их (SVG). Плотности пород — типичные значения, их можно менять.
"""
import math

import quantum
from calc_utils import num

G = 9.80665

ROCKS = {
    "sand": {"name": "Песок / песчаник", "density": 2300, "color": "#d9b86c", "pattern": "dots"},
    "clay": {"name": "Глина / аргиллит", "density": 2200, "color": "#9a7656", "pattern": "lines"},
    "limestone": {"name": "Известняк", "density": 2650, "color": "#8fb8c9", "pattern": "bricks"},
    "shale": {"name": "Сланец", "density": 2600, "color": "#7c8a99", "pattern": "dashes"},
    "salt": {"name": "Каменная соль", "density": 2160, "color": "#d5e1f2", "pattern": "plus"},
    "coal": {"name": "Уголь", "density": 1350, "color": "#23262e", "pattern": "solid"},
    "granite": {"name": "Гранит", "density": 2700, "color": "#c98585", "pattern": "cross"},
    "basalt": {"name": "Базальт", "density": 2950, "color": "#5a5f7d", "pattern": "v"},
}

DEMO_LAYERS = [
    {"rock": "sand", "thickness_m": 150},
    {"rock": "clay", "thickness_m": 450},
    {"rock": "sand", "thickness_m": 900},
    {"rock": "limestone", "thickness_m": 1200},
    {"rock": "shale", "thickness_m": 1100},
    {"rock": "granite", "thickness_m": 1200},
]


def depth_profile(p):
    """Температура и давление от глубины (для графика)."""
    max_km = num(p, "max_depth_km", 6, 0.5, 20)
    steps = int(num(p, "steps", 24, 4, 60))
    t0 = num(p, "surface_temp_c", 15, -50, 60)
    grad = num(p, "gradient_c_per_km", 30, 5, 100)
    rho = num(p, "rock_density_kg_m3", 2700, 1800, 3500)
    rho_w = num(p, "water_density_kg_m3", 1000, 900, 1300)
    points = []
    for i in range(steps + 1):
        z_km = max_km * i / steps
        z = z_km * 1000
        points.append({
            "depth_km": round(z_km, 3),
            "temperature_c": round(t0 + grad * z_km, 2),
            "lithostatic_mpa": round(rho * G * z / 1e6, 2),
            "hydrostatic_mpa": round(rho_w * G * z / 1e6, 2),
        })
    return {"points": points,
            "assumption": "линейный градиент, однородная порода; "
                          "реальные значения зависят от региона и разреза"}


def blackbody_curve(p):
    """Спектр излучения чёрного тела по закону Планка."""
    temp = num(p, "temperature_k", 5772, 200, 50000)
    n = int(num(p, "points", 80, 20, 200))
    lam_peak = quantum.WIEN_B / temp
    lo, hi = 0.2 * lam_peak, 5 * lam_peak

    def radiance(lam):
        x = quantum.H * quantum.C / (lam * quantum.K_B * temp)
        if x > 700:
            return 0.0
        return 2 * quantum.H * quantum.C ** 2 / lam ** 5 / math.expm1(x)

    peak = radiance(lam_peak)
    lams = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    return {
        "temperature_k": temp,
        "peak_nm": round(lam_peak * 1e9, 1),
        "power_w_m2": quantum.SIGMA * temp ** 4,
        "wavelength_nm": [round(l * 1e9, 2) for l in lams],
        "relative": [round(radiance(l) / peak, 5) for l in lams],
        "visible_nm": [380, 750],
        "assumption": "идеальное чёрное тело; кривая нормирована на максимум",
    }


def section(p):
    """Разрез (стратиграфическая колонка): слои, температура и давление на границах."""
    layers_in = p.get("layers") or DEMO_LAYERS
    if not isinstance(layers_in, list) or not 1 <= len(layers_in) <= 12:
        raise ValueError("layers: список из 1-12 слоёв вида {rock, thickness_m}")
    t0 = num(p, "surface_temp_c", 15, -50, 60)
    grad = num(p, "gradient_c_per_km", 30, 5, 100)
    target = num(p, "target_depth_m", None, 1, 30000)

    out, top, p_top = [], 0.0, 0.0
    for i, item in enumerate(layers_in, 1):
        if not isinstance(item, dict):
            raise ValueError(f"слой {i}: нужен объект {{rock, thickness_m}}")
        key = str(item.get("rock", ""))
        if key not in ROCKS:
            raise ValueError(f"слой {i}: неизвестная порода «{key}»")
        rock = ROCKS[key]
        h = num(item, "thickness_m", lo=1, hi=10000)
        rho = num(item, "density_kg_m3", rock["density"], 500, 4000)
        bottom = top + h
        p_bot = p_top + rho * G * h / 1e6
        out.append({
            "rock": key, "name": rock["name"], "color": rock["color"],
            "pattern": rock["pattern"], "density_kg_m3": rho,
            "top_m": round(top, 1), "bottom_m": round(bottom, 1), "thickness_m": h,
            "temp_top_c": round(t0 + grad * top / 1000, 1),
            "temp_bottom_c": round(t0 + grad * bottom / 1000, 1),
            "pressure_top_mpa": round(p_top, 1),
            "pressure_bottom_mpa": round(p_bot, 1),
        })
        top, p_top = bottom, p_bot
    total = top
    if total > 30000:
        raise ValueError("суммарная мощность разреза не больше 30 000 м")

    target_info = None
    if target is not None:
        if target > total:
            raise ValueError("глубина цели больше, чем весь разрез")
        layer = next(l for l in out if l["top_m"] <= target <= l["bottom_m"])
        pressure = layer["pressure_top_mpa"] + layer["density_kg_m3"] * G * (target - layer["top_m"]) / 1e6
        target_info = {
            "depth_m": target,
            "temperature_c": round(t0 + grad * target / 1000, 1),
            "pressure_mpa": round(pressure, 1),
            "layer": layer["name"],
        }
    return {
        "layers": out, "total_depth_m": round(total, 1), "target": target_info,
        "surface_temp_c": t0, "gradient_c_per_km": grad,
        "assumption": "давление — только литостатическое (вес пород); температура — "
                      "линейный градиент, без учёта теплопроводности слоёв",
    }
