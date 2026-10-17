"""Модуль 13 — квантовая физика и энергетика: точные расчёты по формулам.

Константы — точные значения СИ (CODATA 2019).
"""
import math

from calc_utils import num

H = 6.62607015e-34       # Дж·с, постоянная Планка
C = 299792458.0          # м/с
K_B = 1.380649e-23       # Дж/К
E_CH = 1.602176634e-19   # Кл (и Дж на 1 эВ)
SIGMA = 5.670374419e-8   # Вт/(м²·К⁴)
WIEN_B = 2.897771955e-3  # м·К
MASSES = {"electron": 9.1093837015e-31, "proton": 1.67262192369e-27,
          "neutron": 1.67492749804e-27}


def photon(p):
    """Энергия фотона E = h·f = h·c/λ."""
    if "wavelength_nm" in p:
        lam = num(p, "wavelength_nm", lo=1e-6, hi=1e9) * 1e-9
        freq = C / lam
    else:
        freq = num(p, "frequency_hz", lo=1e3, hi=1e25)
        lam = C / freq
    energy = H * freq
    return {
        "wavelength_nm": lam * 1e9,
        "frequency_hz": freq,
        "energy_j": energy,
        "energy_ev": energy / E_CH,
        "momentum_kg_m_s": H / lam,
    }


def blackbody(p):
    """Закон Вина, Стефана-Больцмана и (опционально) закон Планка."""
    temp = num(p, "temperature_k", lo=1, hi=1e8)
    out = {
        "temperature_k": temp,
        "peak_wavelength_nm": WIEN_B / temp * 1e9,
        "power_per_area_w_m2": SIGMA * temp ** 4,
    }
    if "wavelength_nm" in p:
        lam = num(p, "wavelength_nm", lo=1e-3, hi=1e9) * 1e-9
        x = H * C / (lam * K_B * temp)
        if x > 700:  # exp переполнится, излучение ≈ 0
            radiance = 0.0
        else:
            radiance = 2 * H * C ** 2 / lam ** 5 / math.expm1(x)
        out["spectral_radiance_w_sr_m3"] = radiance
    return out


def de_broglie(p):
    """Длина волны де Бройля λ = h / (m·v)."""
    if "particle" in p:
        name = str(p["particle"]).lower()
        if name not in MASSES:
            raise ValueError(f"particle: одно из {', '.join(MASSES)}")
        mass = MASSES[name]
    else:
        mass = num(p, "mass_kg", lo=1e-40, hi=1e10)
    v = num(p, "velocity_m_s", lo=1e-9, hi=0.1 * C)
    lam = H / (mass * v)
    return {"mass_kg": mass, "velocity_m_s": v, "wavelength_m": lam,
            "assumption": "нерелятивистская формула (v ≤ 0.1c)"}


def box(p):
    """Уровни частицы в бесконечной яме: E_n = n²·h² / (8·m·L²)."""
    length = num(p, "length_nm", lo=1e-3, hi=1e6) * 1e-9
    n_max = int(num(p, "n_levels", 3, 1, 20))
    name = str(p.get("particle", "electron")).lower()
    if name not in MASSES:
        raise ValueError(f"particle: одно из {', '.join(MASSES)}")
    m = MASSES[name]
    levels = [
        {"n": n, "energy_ev": n ** 2 * H ** 2 / (8 * m * length ** 2) / E_CH}
        for n in range(1, n_max + 1)
    ]
    return {"particle": name, "length_nm": length * 1e9, "levels": levels}


def photoelectric(p):
    """Фотоэффект: KE_max = h·f − φ."""
    lam = num(p, "wavelength_nm", lo=1, hi=1e5) * 1e-9
    phi = num(p, "work_function_ev", lo=0, hi=50)
    e_ph = H * C / lam / E_CH
    ke = e_ph - phi
    return {
        "photon_energy_ev": e_ph,
        "work_function_ev": phi,
        "ke_max_ev": max(ke, 0.0),
        "emission": ke > 0,
        "threshold_wavelength_nm": (H * C / (phi * E_CH) * 1e9) if phi > 0 else None,
    }


def mass_energy(p):
    """E = m·c²."""
    m = num(p, "mass_kg", lo=0, hi=1e30)
    e = m * C ** 2
    return {"energy_j": e, "energy_kwh": e / 3.6e6}


def carnot(p):
    """Предельный КПД тепловой машины: η = 1 − Tc/Th."""
    th = num(p, "t_hot_k", lo=1, hi=1e5)
    tc = num(p, "t_cold_k", lo=1, hi=1e5)
    if tc >= th:
        raise ValueError("t_cold_k должна быть меньше t_hot_k")
    return {"efficiency_max": 1 - tc / th,
            "assumption": "теоретический предел; реальные машины заметно ниже"}


CALCS = {
    "photon": (photon, "wavelength_nm ИЛИ frequency_hz"),
    "blackbody": (blackbody, "temperature_k, [wavelength_nm]"),
    "de_broglie": (de_broglie, "velocity_m_s, particle (electron|proton|neutron) ИЛИ mass_kg"),
    "box": (box, "length_nm, [particle, n_levels]"),
    "photoelectric": (photoelectric, "wavelength_nm, work_function_ev"),
    "mass_energy": (mass_energy, "mass_kg"),
    "carnot": (carnot, "t_hot_k, t_cold_k"),
}
