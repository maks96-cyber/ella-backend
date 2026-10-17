"""Модули 10 и 12 — роботы, шасси, роботизированное извлечение.

Квазистатические оценки первого приближения: подбор мотор-редукторов,
питания и нагрузок. Для конструкции нужны расчёты по конкретной схеме.
"""
import math

from calc_utils import num

G = 9.80665


def chassis_drive(p):
    """Тяговое усилие, момент на колесо и мощность привода шасси."""
    m = num(p, "mass_kg", lo=0.1, hi=1e6)
    slope = math.radians(num(p, "slope_deg", 0, 0, 45))
    crr = num(p, "rolling_resistance", 0.05, 0.005, 0.5)
    r = num(p, "wheel_radius_m", lo=0.01, hi=5)
    wheels = int(num(p, "driven_wheels", 4, 1, 12))
    v = num(p, "speed_m_s", 1.0, 0, 50)
    acc = num(p, "accel_m_s2", 0, 0, 20)
    eff = num(p, "efficiency", 0.8, 0.2, 1.0)

    force = m * G * (math.sin(slope) + crr * math.cos(slope)) + m * acc
    torque_wheel = force * r / wheels / eff
    power = force * v / eff
    mu_needed = (math.sin(slope) + crr * math.cos(slope) + acc / G) / math.cos(slope)
    return {
        "traction_force_n": round(force, 1),
        "torque_per_wheel_nm": round(torque_wheel, 2),
        "power_w": round(power, 1),
        "min_traction_coefficient": round(mu_needed, 3),
        "assumption": "квазистатика, без проскальзывания и сопротивления воздуха; "
                      "трение колёс о грунт должно быть выше min_traction_coefficient; "
                      "для мягкого грунта rolling_resistance 0.1-0.3",
    }


def battery_runtime(p):
    """Время работы от аккумулятора."""
    cap = num(p, "capacity_wh", lo=0.1, hi=1e7)
    power = num(p, "power_w", lo=0.01, hi=1e7)
    usable = num(p, "usable_fraction", 0.8, 0.1, 1.0)
    hours = cap * usable / power
    return {"hours": round(hours, 2), "minutes": round(hours * 60, 1),
            "assumption": "постоянная мощность; ёмкость падает на холоде и при больших токах"}


def drill_string_load(p):
    """Вес бурильной колонны в воздухе и в буровом растворе (с учётом плавучести)."""
    length = num(p, "length_m", lo=1, hi=30000)
    mpm = num(p, "mass_per_m_kg", 29, 1, 500)
    mud = num(p, "mud_density_kg_m3", 1200, 800, 2800)
    steel = num(p, "steel_density_kg_m3", 7850, 7000, 8500)
    buoy = 1 - mud / steel
    air = length * mpm * G / 1000
    return {
        "buoyancy_factor": round(buoy, 4),
        "weight_in_air_kn": round(air, 1),
        "weight_in_mud_kn": round(air * buoy, 1),
        "assumption": "однородная колонна; не учтены утяжелённые трубы, замки, трение "
                      "о стенки и запас на натяжение — это решает инженер по бурению",
    }


CALCS = {
    "chassis_drive": (chassis_drive, "mass_kg, wheel_radius_m, [slope_deg, rolling_resistance, driven_wheels, speed_m_s, accel_m_s2, efficiency]"),
    "battery_runtime": (battery_runtime, "capacity_wh, power_w, [usable_fraction]"),
    "drill_string_load": (drill_string_load, "length_m, [mass_per_m_kg, mud_density_kg_m3]"),
}
