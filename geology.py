"""Модуль 9 — глубинная геология (4-5+ км): инженерные оценки.

Упрощённые модели первого приближения для планирования и обучения.
Для реального бурения нужны данные по конкретному разрезу и расчёт
буровой компанией/геологом.
"""
import math

from calc_utils import num

G = 9.80665  # м/с²


def thermal(p):
    """Температура на глубине: T = T0 + градиент · глубина."""
    depth = num(p, "depth_km", lo=0, hi=20)
    t0 = num(p, "surface_temp_c", 15, -50, 60)
    grad = num(p, "gradient_c_per_km", 30, 5, 100)
    return {
        "depth_km": depth,
        "temperature_c": round(t0 + grad * depth, 1),
        "range_c": [round(t0 + 20 * depth, 1), round(t0 + 40 * depth, 1)],
        "assumption": "линейный градиент (типично 20-40 °C/км для континентов); "
                      "в диапазоне — градиенты 20 и 40",
    }


def pressure(p):
    """Литостатическое и гидростатическое давление: P = ρ·g·h."""
    depth_m = num(p, "depth_km", lo=0, hi=20) * 1000
    rho_rock = num(p, "rock_density_kg_m3", 2700, 1800, 3500)
    rho_water = num(p, "water_density_kg_m3", 1000, 900, 1300)
    litho = rho_rock * G * depth_m / 1e6
    hydro = rho_water * G * depth_m / 1e6
    out = {
        "depth_km": depth_m / 1000,
        "lithostatic_mpa": round(litho, 1),
        "hydrostatic_mpa": round(hydro, 1),
        "hydrostatic_to_lithostatic": round(hydro / litho, 3) if litho else None,
    }
    if "pore_pressure_mpa" in p:
        pore = num(p, "pore_pressure_mpa", lo=0)
        out["pore_pressure_mpa"] = pore
        out["overpressure_vs_hydrostatic_mpa"] = round(pore - hydro, 1)
    return out


def drilling_mud(p):
    """Статическое давление бурового раствора и запас до давлений пласта."""
    depth_m = num(p, "depth_km", lo=0, hi=20) * 1000
    mud = num(p, "mud_density_kg_m3", 1200, 800, 2800)
    mud_mpa = mud * G * depth_m / 1e6
    hydro = 1000 * G * depth_m / 1e6
    pore = num(p, "pore_pressure_mpa", hydro, 0, None)
    out = {
        "mud_pressure_mpa": round(mud_mpa, 1),
        "pore_pressure_mpa": round(pore, 1),
        "overbalance_mpa": round(mud_mpa - pore, 1),
    }
    status = "в окне: давление раствора выше порового"
    if mud_mpa < pore:
        status = "НЕДОБАЛАНС: давление раствора ниже порового — риск притока/выброса"
    if "fracture_pressure_mpa" in p:
        frac = num(p, "fracture_pressure_mpa", lo=0)
        out["fracture_pressure_mpa"] = frac
        out["margin_to_fracture_mpa"] = round(frac - mud_mpa, 1)
        if mud_mpa > frac:
            status = "ВЫШЕ давления разрыва пласта — риск поглощения раствора"
    out["status"] = status
    out["assumption"] = ("статика без потерь на циркуляцию (ECD); "
                         "по умолчанию поровое = гидростатическое для воды 1000 кг/м³")
    return out


def drill_time(p):
    """Время бурения по средней механической скорости проходки (ROP)."""
    depth_m = num(p, "depth_km", lo=0, hi=20) * 1000
    rop = num(p, "rop_m_per_h", 5, 0.5, 100)
    bit_life = num(p, "bit_life_h", 60, 5, 500)
    trip_h = num(p, "trip_hours_per_bit", 24, 0, 200)
    drilling_h = depth_m / rop
    bit_changes = max(0, math.ceil(drilling_h / bit_life) - 1)
    total_h = drilling_h + bit_changes * trip_h
    return {
        "drilling_hours": round(drilling_h, 1),
        "bit_changes": bit_changes,
        "total_hours": round(total_h, 1),
        "total_days": round(total_h / 24, 1),
        "assumption": "постоянный ROP; на глубине 4-5 км он обычно заметно падает",
    }


def geothermal_power(p):
    """Тепловая мощность потока: Q = m · cp · ΔT (и электрическая при КПД)."""
    flow = num(p, "flow_kg_s", lo=0, hi=5000)
    dt = num(p, "delta_t_c", lo=0, hi=300)
    cp = num(p, "cp_j_kg_k", 4186, 2000, 5000)
    thermal_mw = flow * cp * dt / 1e6
    eff = num(p, "efficiency", 0.10, 0.01, 0.5)
    return {
        "thermal_mw": round(thermal_mw, 2),
        "electric_mw": round(thermal_mw * eff, 2),
        "efficiency_used": eff,
        "assumption": "для 120-160 °C типичный КПД бинарных ORC-установок ~8-15%",
    }


CALCS = {
    "thermal": (thermal, "depth_km, [surface_temp_c, gradient_c_per_km]"),
    "pressure": (pressure, "depth_km, [rock_density_kg_m3, water_density_kg_m3, pore_pressure_mpa]"),
    "drilling_mud": (drilling_mud, "depth_km, [mud_density_kg_m3, pore_pressure_mpa, fracture_pressure_mpa]"),
    "drill_time": (drill_time, "depth_km, [rop_m_per_h, bit_life_h, trip_hours_per_bit]"),
    "geothermal_power": (geothermal_power, "flow_kg_s, delta_t_c, [cp_j_kg_k, efficiency]"),
}
