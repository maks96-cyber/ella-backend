"""Модули 8, 14, 15 — спутниковая связь, орбиты, ионная логистика.

Формулы первого приближения для оценок и обучения, не для проектных решений.
"""
import math

from calc_utils import num

C = 299792458.0
G0 = 9.80665
MU_EARTH = 3.986004418e14   # м3/с2
R_EARTH = 6371.0            # км, средний радиус
MU_SUN = 1.32712440018e20   # м3/с2
AU = 1.495978707e11         # м


def link_budget(p):
    """Потери в свободном пространстве и мощность на приёме (GNSS / Direct-to-Cell)."""
    d = num(p, "distance_km", lo=1, hi=1e9)
    f = num(p, "frequency_mhz", lo=1, hi=1e6)
    fspl = 20 * math.log10(d) + 20 * math.log10(f) + 32.44
    out = {
        "fspl_db": round(fspl, 2),
        "delay_ms": round(d * 1000 / C * 1000, 3),
        "assumption": "только потери свободного пространства; атмосфера, дождь, "
                      "поляризация и многолучёвость не учтены",
    }
    if "eirp_dbw" in p:
        eirp = num(p, "eirp_dbw", lo=-100, hi=100)
        gain = num(p, "rx_gain_dbi", 0, -50, 80)
        loss = num(p, "other_losses_db", 0, 0, 100)
        out["rx_power_dbw"] = round(eirp - fspl + gain - loss, 2)
        out["rx_power_dbm"] = round(eirp - fspl + gain - loss + 30, 2)
    return out


def slant_range(p):
    """Наклонная дальность до спутника по высоте орбиты и углу места."""
    h = num(p, "altitude_km", lo=100, hi=100000)
    el = math.radians(num(p, "elevation_deg", 90, 0, 90))
    r = R_EARTH
    rng = math.sqrt((r + h) ** 2 - (r * math.cos(el)) ** 2) - r * math.sin(el)
    return {"slant_range_km": round(rng, 1),
            "delay_ms": round(rng * 1000 / C * 1000, 3),
            "assumption": "круговая орбита, сферическая Земля"}


def orbit(p):
    """Период и скорость круговой орбиты вокруг Земли."""
    h = num(p, "altitude_km", lo=100, hi=1e6)
    a = (R_EARTH + h) * 1000
    period = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    return {"period_min": round(period / 60, 2),
            "period_h": round(period / 3600, 3),
            "velocity_km_s": round(math.sqrt(MU_EARTH / a) / 1000, 3)}


def rocket_delta_v(p):
    """Уравнение Циолковского: Δv = Isp·g0·ln(m0/mf)."""
    isp = num(p, "isp_s", lo=1, hi=1e5)
    if "delta_v_m_s" in p:
        dv = num(p, "delta_v_m_s", lo=0, hi=1e6)
        ratio = math.exp(dv / (isp * G0))
        return {"mass_ratio": round(ratio, 4),
                "propellant_fraction": round(1 - 1 / ratio, 4)}
    m0 = num(p, "mass_initial_kg", lo=0.001, hi=1e9)
    mf = num(p, "mass_final_kg", lo=0.001, hi=m0)
    return {"delta_v_m_s": round(isp * G0 * math.log(m0 / mf), 1),
            "propellant_kg": round(m0 - mf, 3)}


def ion_thruster(p):
    """Ионный двигатель: тяга из мощности, КПД и удельного импульса."""
    power = num(p, "power_kw", lo=0.001, hi=1e4) * 1000
    isp = num(p, "isp_s", lo=100, hi=1e5)
    eff = num(p, "efficiency", 0.6, 0.05, 0.95)
    ve = isp * G0
    thrust = 2 * eff * power / ve
    out = {"thrust_n": round(thrust, 4),
           "exhaust_velocity_m_s": round(ve, 1),
           "mass_flow_mg_s": round(thrust / ve * 1e6, 3)}
    if "spacecraft_mass_kg" in p:
        m = num(p, "spacecraft_mass_kg", lo=1, hi=1e9)
        out["acceleration_mm_s2"] = round(thrust / m * 1000, 4)
        out["delta_v_per_day_m_s"] = round(thrust / m * 86400, 2)
    out["assumption"] = "тяга = 2·η·P/(g0·Isp); потери питания и массу ЭУ не учитывает"
    return out


def hohmann(p):
    """Перелёт по Гоману между круговыми гелиоцентрическими орбитами."""
    r1 = num(p, "r1_au", 1.0, 0.1, 100) * AU
    r2 = num(p, "r2_au", 2.92, 0.1, 100) * AU
    dv1 = math.sqrt(MU_SUN / r1) * (math.sqrt(2 * r2 / (r1 + r2)) - 1)
    dv2 = math.sqrt(MU_SUN / r2) * (1 - math.sqrt(2 * r1 / (r1 + r2)))
    t = math.pi * math.sqrt(((r1 + r2) / 2) ** 3 / MU_SUN)
    return {"dv_departure_km_s": round(abs(dv1) / 1000, 3),
            "dv_arrival_km_s": round(abs(dv2) / 1000, 3),
            "dv_total_km_s": round((abs(dv1) + abs(dv2)) / 1000, 3),
            "transfer_days": round(t / 86400, 1),
            "assumption": "импульсный перелёт между круговыми орбитами в одной плоскости; "
                          "для ионной тяги реальная схема (спираль) иная. "
                          "Значение 2.92 а.е. по умолчанию — приблизительная орбита Психеи (16 Psyche)."}


CALCS = {
    "link_budget": (link_budget, "distance_km, frequency_mhz, [eirp_dbw, rx_gain_dbi, other_losses_db]"),
    "slant_range": (slant_range, "altitude_km, [elevation_deg]"),
    "orbit": (orbit, "altitude_km"),
    "rocket_delta_v": (rocket_delta_v, "isp_s, (mass_initial_kg, mass_final_kg) ИЛИ delta_v_m_s"),
    "ion_thruster": (ion_thruster, "power_kw, isp_s, [efficiency, spacecraft_mass_kg]"),
    "hohmann": (hohmann, "[r1_au, r2_au]"),
}
