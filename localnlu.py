"""Локальный движок Эллы: понимает расчётные вопросы по-русски и считает без ИИ.

Без внешних библиотек и без сети. Находит нужный расчёт по ключевым словам,
вытаскивает числа с единицами (км, м/с, МПа, кВт, нм ...) и вызывает те же
калькуляторы, что и ИИ-инструменты. Это не языковая модель: свободно
рассуждать и объяснять он не умеет, зато точен и работает всегда.
"""
import re

import tools

NUM = r"(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)"
END = r"(?![a-zа-я0-9/²³])"

# ---------- Единицы: (шаблон, множитель к базовой единице параметра) ----------
KM = [(r"км|километр\w*", 1.0), (r"м|метр\w*", 1e-3)]
NM = [(r"нм|nm|нанометр\w*", 1.0), (r"мкм|микрометр\w*|микрон\w*", 1e3),
      (r"мм|миллиметр\w*", 1e6), (r"м|метр\w*", 1e9)]
HZ = [(r"гц|hz|герц\w*", 1.0), (r"кгц|khz", 1e3), (r"мгц|mhz", 1e6), (r"ггц|ghz", 1e9), (r"тгц|thz", 1e12)]
MHZ = [(r"мгц|mhz", 1.0), (r"ггц|ghz", 1e3), (r"кгц|khz", 1e-3)]
MS = [(r"м/с|m/s", 1.0), (r"км/с|km/s", 1e3)]
KG = [(r"кг|kg|килограмм\w*", 1.0), (r"т|тонн\w*", 1e3), (r"г|грамм\w*", 1e-3), (r"мг", 1e-6)]
KW = [(r"квт|kw|киловатт\w*", 1.0), (r"вт|w|ватт\w*", 1e-3), (r"мвт|mw|мегаватт\w*", 1e3)]
KELVIN = [(r"к|k|кельвин\w*", 1.0)]
MPA = [(r"мпа|mpa|мегапаскал\w*", 1.0), (r"кпа|kpa|килопаскал\w*", 1e-3), (r"гпа|gpa|гигапаскал\w*", 1e3), (r"бар\w*", 0.1), (r"атм\w*", 0.101325)]
DENS = [(r"кг/м3|кг/м³|кг/м\^3|кг/куб\w*", 1.0), (r"г/см3|г/см³", 1e3)]
MM = [(r"мм|миллиметр\w*", 1.0), (r"см|сантиметр\w*", 10.0), (r"м|метр\w*", 1000.0)]
M_ = [(r"мм", 1e-3), (r"см", 1e-2), (r"м|метр\w*", 1.0)]
DEG = [(r"°|градус\w*|deg", 1.0)]
EV = [(r"эв|ev", 1.0)]
WH = [(r"квт[·*. ]?ч|kwh", 1e3), (r"вт[·*. ]?ч|wh", 1.0)]
NM_TORQUE = [(r"н[·*. ]?м|nm|ньютон\w*[ -]*метр\w*", 1.0)]
RPM = [(r"об/мин|об\./мин|rpm|оборот\w*(?: в минут\w*)?", 1.0)]
AU = [(r"а\.? ?е\.?|au|астрономическ\w+ единиц\w*", 1.0)]
KGS = [(r"кг/с|kg/s|л/с", 1.0)]
MPH = [(r"м/ч|м/час\w*", 1.0)]
KGM = [(r"кг/м|kg/m", 1.0)]
SPEED = [(r"м/с|m/s", 1.0), (r"км/ч", 1 / 3.6)]
ACC = [(r"м/с2|м/с²|m/s2", 1.0)]


def norm(text: str) -> str:
    t = text.lower().replace("ё", "е")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"\b(\d{1,3})((?: \d{3})+)\b", lambda m: m.group(1) + m.group(2).replace(" ", ""), t)
    t = re.sub(r"(?<=\d)\s*[x×*·]\s*10\^?\s*(-?\d+)", r"e\1", t)
    return re.sub(r"\s+", " ", t).strip()


def find(t, units=None, after=None, window=40, skip=None):
    """Число: (значение, начало, конец) или None. units — обязательные единицы,
    after — ключевое слово перед числом, skip — диапазоны текста, которые игнорировать."""
    scope, off = t, 0
    if after:
        m = re.search(after, t)
        if not m:
            return None
        scope, off = t[m.end(): m.end() + window], m.end()
    best = None
    if units:
        for pat, f in units:
            for m in re.finditer(NUM + r"\s*(?:" + pat + r")" + END, scope):
                s = off + m.start()
                if skip and any(a <= s < b for a, b in skip):
                    continue
                if best is None or s < best[1]:
                    best = (float(m.group(1)) * f, s, off + m.end())
                break
        return best
    m = re.search(NUM, scope)
    return (float(m.group(1)), off + m.start(), off + m.end()) if m else None


def val(*hits):
    for h in hits:
        if h:
            return h[0]
    return None


def find_all(t, units):
    out = []
    for pat, f in units:
        for m in re.finditer(NUM + r"\s*(?:" + pat + r")" + END, t):
            out.append((m.start(), float(m.group(1)) * f))
    return [v for _, v in sorted(out)]


def percent(v):
    return None if v is None else (v / 100 if v > 1 else v)


def put(a, key, v):
    if v is not None:
        a[key] = v


def depth(t):
    return val(find(t, KM, after=r"глубин\w*", window=25), find(t, KM))


PARTICLES = {"электрон": "electron", "протон": "proton", "нейтрон": "neutron"}


def particle(t):
    for ru, en in PARTICLES.items():
        if ru in t:
            return en
    return None


# ---------- Правила: инструмент, обязательные признаки, извлечение параметров ----------
def r_drilling_mud(t):
    a = {}
    put(a, "depth_km", depth(t))
    put(a, "mud_density_kg_m3", val(find(t, DENS, after=r"плотност\w*"), find(t, DENS)))
    put(a, "pore_pressure_mpa", val(find(t, MPA, after=r"поров\w*")))
    put(a, "fracture_pressure_mpa", val(find(t, MPA, after=r"(?:разрыв\w*|гидроразрыв\w*)")))
    return a


def r_drill_time(t):
    a = {}
    put(a, "depth_km", depth(t))
    put(a, "rop_m_per_h", val(find(t, MPH)))
    put(a, "bit_life_h", val(find(t, after=r"ресурс\w* долот\w*", window=20)))
    return a


def r_geo_power(t):
    a = {}
    put(a, "flow_kg_s", val(find(t, KGS)))
    put(a, "delta_t_c", val(find(t, after=r"(?:перепад\w*|разниц\w*|дельта)", window=25)))
    put(a, "efficiency", percent(val(find(t, after=r"кпд", window=15))))
    return a


def r_pressure(t):
    a = {}
    put(a, "depth_km", depth(t))
    put(a, "rock_density_kg_m3", val(find(t, DENS, after=r"плотност\w*")))
    put(a, "pore_pressure_mpa", val(find(t, MPA, after=r"поров\w*")))
    return a


def r_thermal(t):
    a = {}
    put(a, "depth_km", depth(t))
    put(a, "gradient_c_per_km", val(find(t, after=r"градиент\w*", window=25)))
    put(a, "surface_temp_c", val(find(t, after=r"на поверхност\w*", window=20)))
    return a


def r_photoelectric(t):
    a = {}
    put(a, "wavelength_nm", val(find(t, NM)))
    put(a, "work_function_ev", val(find(t, after=r"работ\w* выхода", window=25)))
    return a


def r_photon(t):
    a = {}
    wl = val(find(t, NM))
    fr = val(find(t, HZ))
    put(a, "wavelength_nm", wl)
    if wl is None:
        put(a, "frequency_hz", fr)
    return a


def r_blackbody(t):
    a = {}
    put(a, "temperature_k", val(find(t, KELVIN), find(t, after=r"температур\w*", window=20)))
    put(a, "wavelength_nm", val(find(t, NM, after=r"длин\w* волны")))
    return a


def r_de_broglie(t):
    a = {}
    put(a, "velocity_m_s", val(find(t, MS), find(t, after=r"скорост\w*", window=25)))
    p = particle(t)
    if p:
        a["particle"] = p
    else:
        put(a, "mass_kg", val(find(t, KG)))
    return a


def r_box(t):
    a = {}
    put(a, "length_nm", val(find(t, NM), find(t, [(r"ангстрем\w*|å", 0.1)])))
    m = re.search(r"перв\w* (\d+) уровн|(\d+) уровн", t)
    if m:
        a["n_levels"] = int(m.group(1) or m.group(2))
    p = particle(t)
    if p:
        a["particle"] = p
    return a


def r_mass_energy(t):
    a = {}
    put(a, "mass_kg", val(find(t, KG)))
    return a


def r_carnot(t):
    temps = find_all(t, KELVIN)
    if len(temps) < 2:
        cel = find_all(t, [(r"°c|°с|градус\w*", 1.0)])
        temps = [c + 273.15 for c in cel] if len(cel) >= 2 else temps
    a = {}
    if len(temps) >= 2:
        a["t_hot_k"], a["t_cold_k"] = max(temps[:2]), min(temps[:2])
    return a


def r_shaft(t):
    a = {}
    torque = find(t, NM_TORQUE)
    skip = [(torque[1], torque[2])] if torque else None
    put(a, "torque_nm", val(torque))
    put(a, "power_kw", val(find(t, KW, skip=skip)))
    put(a, "rpm", val(find(t, RPM)))
    put(a, "allowable_shear_mpa", val(find(t, MPA, after=r"(?:напряжен\w*|допускаем\w*)")))
    return a


def r_bolts(t):
    a = {}
    put(a, "bolt_circle_d", val(find(t, MM, after=r"окружност\w*", window=30), find(t, MM)))
    m = re.search(r"(\d+)\s*(?:отверсти\w*|болт\w*|шпильк\w*)", t)
    if m:
        a["bolt_count"] = int(m.group(1))
    put(a, "start_angle_deg", val(find(t, after=r"(?:начальн\w* угол|угол)", window=15)))
    return a


def r_link(t):
    a = {}
    f = val(find(t, MHZ))
    if f is None:
        return None
    a["frequency_mhz"] = f
    put(a, "distance_km", val(find(t, KM, after=r"(?:дальност\w*|расстояни\w*|высот\w*)", window=25), find(t, KM)))
    put(a, "eirp_dbw", val(find(t, after=r"(?:эиим|eirp)", window=15)))
    put(a, "rx_gain_dbi", val(find(t, after=r"усилени\w*", window=15)))
    return a


def r_slant(t):
    a = {}
    put(a, "altitude_km", val(find(t, KM, after=r"высот\w*", window=25), find(t, KM)))
    put(a, "elevation_deg", val(find(t, DEG, after=r"угол\w* мест\w*", window=20), find(t, after=r"угол\w* мест\w*", window=15)))
    return a


def r_orbit(t):
    a = {}
    put(a, "altitude_km", val(find(t, KM, after=r"высот\w*", window=25), find(t, KM)))
    return a


def r_ion(t):
    a = {}
    put(a, "power_kw", val(find(t, KW)))
    put(a, "isp_s", val(find(t, after=r"(?:удельн\w* импульс\w*|isp)", window=25), find(t, [(r"с|сек\w*|секунд\w*", 1.0)])))
    put(a, "efficiency", percent(val(find(t, after=r"кпд", window=15))))
    put(a, "spacecraft_mass_kg", val(find(t, KG, after=r"масс\w* (?:аппарат\w*|корабл\w*|спутник\w*)", window=25)))
    return a


def r_rocket(t):
    a = {}
    put(a, "isp_s", val(find(t, after=r"(?:удельн\w* импульс\w*|isp)", window=25)))
    m0 = val(find(t, KG, after=r"(?:начальн\w* масс\w*|стартов\w* масс\w*|масс\w* с топлив\w*)", window=30))
    mf = val(find(t, KG, after=r"(?:конечн\w* масс\w*|сух\w* масс\w*|масс\w* без топлив\w*)", window=30))
    if m0 is None and mf is None:
        masses = find_all(t, KG)
        if len(masses) >= 2:
            m0, mf = max(masses[:2]), min(masses[:2])
    put(a, "mass_initial_kg", m0)
    put(a, "mass_final_kg", mf)
    put(a, "delta_v_m_s", val(find(t, MS, after=r"(?:delta[ -]?v|дельта[ -]?v?|характеристическ\w* скорост\w*|нужн\w* скорост\w*)", window=30)))
    return a


PLANETS = {"меркур": 0.387, "венер": 0.723, "марс": 1.524, "юпитер": 5.203, "сатурн": 9.537}


def r_hohmann(t):
    a = {}
    au = find_all(t, AU)
    for name, r in PLANETS.items():
        if name in t:
            a["r2_au"] = r
            break
    else:
        if len(au) >= 2:
            a["r1_au"], a["r2_au"] = au[0], au[1]
        elif len(au) == 1:
            a["r2_au"] = au[0]
    if re.search(r"психе|psyche", t) and "r2_au" not in a:
        a["r2_au"] = 2.92
    return a or None


def r_chassis(t):
    a = {}
    mass = val(find(t, KG))
    if mass is None:
        return None
    a["mass_kg"] = mass
    r = val(find(t, M_, after=r"радиус\w* колес\w*", window=25))
    if r is None:
        d = val(find(t, M_, after=r"диаметр\w* колес\w*", window=25))
        r = d / 2 if d is not None else None
    put(a, "wheel_radius_m", r)
    put(a, "slope_deg", val(find(t, DEG, after=r"(?:уклон\w*|подъем\w*|склон\w*|горк\w*)", window=25), find(t, DEG)))
    m = re.search(r"(\d+)\s*(?:ведущ\w*|колес\w*)", t)
    if m:
        a["driven_wheels"] = int(m.group(1))
    put(a, "speed_m_s", val(find(t, SPEED)))
    put(a, "accel_m_s2", val(find(t, ACC)))
    put(a, "efficiency", percent(val(find(t, after=r"кпд", window=15))))
    return a


def r_battery(t):
    a = {}
    cap = find(t, WH)
    put(a, "capacity_wh", val(cap))
    skip = [(cap[1], cap[2])] if cap else None
    put(a, "power_w", val(find(t, [(r"вт|w|ватт\w*", 1.0), (r"квт|kw|киловатт\w*", 1e3)], skip=skip)))
    put(a, "usable_fraction", percent(val(find(t, after=r"(?:использу\w*|доступн\w*)", window=20))))
    return a


def r_drill_string(t):
    a = {}
    put(a, "length_m", val(find(t, [(r"м|метр\w*", 1.0), (r"км|километр\w*", 1e3)], after=r"длин\w*", window=25),
                          find(t, [(r"км|километр\w*", 1e3), (r"м|метр\w*", 1.0)])))
    put(a, "mass_per_m_kg", val(find(t, KGM)))
    put(a, "mud_density_kg_m3", val(find(t, DENS)))
    return a


# Порядок важен: более специфичные правила — выше
RULES = [
    ("geology_drilling_mud", [r"(?:буров\w* раствор|раствор\w* бур)", r"давлен|плотност|глубин"], r_drilling_mud),
    ("geology_drill_time", [r"бур\w*|пробур\w*", r"сколько|врем\w*|долго|сут|час|дн"], r_drill_time),
    ("robotics_drill_string_load", [r"бурильн\w* (?:колонн|труб)|вес\w* колонн|колонн\w* бурильн"], r_drill_string),
    ("geology_geothermal_power", [r"геотермальн|термальн\w* (?:вод|поток|скважин)", r"мощност|энерги|поток|расход"], r_geo_power),
    ("geology_pressure", [r"давлен", r"глубин|\d\s*(?:км|м)\b"], r_pressure),
    ("geology_thermal", [r"температур", r"глубин|\d\s*км"], r_thermal),
    ("quantum_photoelectric", [r"фотоэффект|работ\w* выхода"], r_photoelectric),
    ("quantum_photon", [r"фотон|квант\w* свет|энерги\w* (?:света|кванта)"], r_photon),
    ("quantum_de_broglie", [r"бройл"], r_de_broglie),
    ("quantum_box", [r"яма|ямы|яме|ящик\w*", r"уровн|энерги"], r_box),
    ("quantum_carnot", [r"карно"], r_carnot),
    ("quantum_mass_energy", [r"e\s*=\s*mc|эквивалент|энерги\w* (?:покоя|массы)|аннигил"], r_mass_energy),
    ("quantum_blackbody", [r"черн\w* тел|закон\w* (?:планка|вина|стефан)|планк|излучени\w* (?:звезд|солнц|тела)"], r_blackbody),
    ("cad_shaft_diameter", [r"\bвал(?:а|у|е|ом|ы|ов)?\b", r"диаметр|сечени|размер"], r_shaft),
    ("cad_bolt_pattern", [r"болт\w*|отверсти\w*|шпильк\w*", r"окружност|pcd"], r_bolts),
    ("space_link_budget", [r"потер\w*|затухан\w*|fspl|энергобюджет|бюджет|уровень сигнала|мощност\w* сигнала", r"спутник|сигнал|канал|связ|линии|gps|gnss"], r_link),
    ("space_slant_range", [r"наклонн\w* дальност|угол\w* мест|дальност\w* до спутник|задержк\w* (?:сигнал|связ)"], r_slant),
    ("space_orbit", [r"орбит", r"период|скорост|оборот\w* вокруг"], r_orbit),
    ("space_ion_thruster", [r"ионн\w* двигател|ионник|электрореактивн|плазменн\w* двигател"], r_ion),
    ("space_rocket_delta_v", [r"циолковск|дельта[ -]?v|delta[ -]?v|ракетн\w* уравнен|характеристическ\w* скорост"], r_rocket),
    ("space_hohmann", [r"гоман|перел[её]т|переход\w* (?:на|между) орбит", r"а\.? ?е\.?|au|марс|венер|юпитер|сатурн|меркур|психе|psyche"], r_hohmann),
    ("robotics_chassis_drive", [r"шасси|робот\w*|тележк\w*|вездеход\w*|ровер\w*", r"момент|мощност|тяг\w*|мотор|привод"], r_chassis),
    ("robotics_battery_runtime", [r"аккумулятор\w*|батаре\w*|акб", r"врем\w*|хватит|проработ\w*|работ\w*"], r_battery),
]

EXPLAIN = re.compile(r"\b(объясни\w*|расскажи\w*|поясни\w*|почему|зачем|что такое|как работает|как устроен\w*|чем отличается|в чем разница|что значит)\b")


def wants_explanation(text: str) -> bool:
    return bool(EXPLAIN.search(norm(text)))


# ---------- Оформление результата ----------
LABELS = {
    "temperature_c": ("Температура", "°C"), "lithostatic_mpa": ("Литостатическое давление", "МПа"),
    "hydrostatic_mpa": ("Гидростатическое давление", "МПа"),
    "overpressure_vs_hydrostatic_mpa": ("Избыток над гидростатическим", "МПа"),
    "mud_pressure_mpa": ("Давление раствора", "МПа"), "pore_pressure_mpa": ("Поровое давление", "МПа"),
    "overbalance_mpa": ("Превышение над поровым", "МПа"), "margin_to_fracture_mpa": ("Запас до разрыва пласта", "МПа"),
    "status": ("Оценка", ""), "drilling_hours": ("Чистое бурение", "ч"), "bit_changes": ("Замен долот", ""),
    "total_hours": ("Всего с подъёмами", "ч"), "total_days": ("Всего", "сут"),
    "thermal_mw": ("Тепловая мощность", "МВт"), "electric_mw": ("Электрическая мощность", "МВт"),
    "wavelength_nm": ("Длина волны", "нм"), "frequency_hz": ("Частота", "Гц"), "energy_j": ("Энергия", "Дж"),
    "energy_ev": ("Энергия", "эВ"), "momentum_kg_m_s": ("Импульс", "кг·м/с"),
    "peak_wavelength_nm": ("Пик излучения", "нм"), "power_per_area_w_m2": ("Мощность с 1 м² поверхности", "Вт"),
    "spectral_radiance_w_sr_m3": ("Спектральная яркость", "Вт/(ср·м³)"),
    "wavelength_m": ("Длина волны де Бройля", "м"), "photon_energy_ev": ("Энергия фотона", "эВ"),
    "ke_max_ev": ("Макс. энергия электронов", "эВ"), "threshold_wavelength_nm": ("Красная граница", "нм"),
    "energy_kwh": ("Энергия", "кВт·ч"), "efficiency_max": ("Предельный КПД", ""),
    "d_min_mm": ("Минимальный диаметр вала", "мм"), "d_round_up_mm": ("С округлением вверх", "мм"),
    "torque_nm": ("Крутящий момент", "Н·м"), "fspl_db": ("Потери в свободном пространстве", "дБ"),
    "delay_ms": ("Задержка сигнала", "мс"), "rx_power_dbw": ("Мощность на приёме", "дБВт"),
    "rx_power_dbm": ("Мощность на приёме", "дБм"), "slant_range_km": ("Наклонная дальность", "км"),
    "period_min": ("Период обращения", "мин"), "period_h": ("Период обращения", "ч"),
    "velocity_km_s": ("Орбитальная скорость", "км/с"), "delta_v_m_s": ("Дельта-v", "м/с"),
    "propellant_kg": ("Расход топлива", "кг"), "mass_ratio": ("Отношение масс", ""),
    "propellant_fraction": ("Доля топлива", ""), "thrust_n": ("Тяга", "Н"),
    "exhaust_velocity_m_s": ("Скорость истечения", "м/с"), "mass_flow_mg_s": ("Расход рабочего тела", "мг/с"),
    "acceleration_mm_s2": ("Ускорение", "мм/с²"), "delta_v_per_day_m_s": ("Прирост скорости за сутки", "м/с"),
    "dv_departure_km_s": ("Разгон на старте", "км/с"), "dv_arrival_km_s": ("Торможение на финише", "км/с"),
    "dv_total_km_s": ("Суммарная дельта-v", "км/с"), "transfer_days": ("Время перелёта", "сут"),
    "traction_force_n": ("Тяговое усилие", "Н"), "torque_per_wheel_nm": ("Момент на колесо", "Н·м"),
    "power_w": ("Мощность привода", "Вт"), "min_traction_coefficient": ("Нужное сцепление колёс с грунтом", ""),
    "hours": ("Время работы", "ч"), "minutes": ("Время работы", "мин"),
    "buoyancy_factor": ("Коэффициент плавучести", ""), "weight_in_air_kn": ("Вес в воздухе", "кН"),
    "weight_in_mud_kn": ("Вес в растворе", "кН"),
}
SKIP_IF = {"energy_j": "energy_ev", "period_min": None}


def fnum(v) -> str:
    if isinstance(v, bool):
        return "да" if v else "нет"
    if not isinstance(v, (int, float)):
        return str(v)
    a = abs(v)
    if a == 0:
        return "0"
    if a >= 1000:
        return f"{v:,.0f}".replace(",", " ")
    if a >= 1e-3:
        return f"{v:.3g}"
    return f"{v:.3e}"


def format_result(tool: str, res: dict) -> str:
    lines = []
    for key, v in res.items():
        if key in ("assumption", "points_mm", "levels", "range_c", "emission") or key not in LABELS:
            continue
        name, unit = LABELS[key]
        if key == "efficiency_max":
            lines.append(f"{name}: {v * 100:.1f}%")
        elif key == "propellant_fraction":
            lines.append(f"{name}: {v * 100:.1f}%")
        else:
            lines.append(f"{name}: {fnum(v)}{(' ' + unit) if unit else ''}")
    if "range_c" in res:
        lines.append(f"Диапазон при градиенте 20-40 °C/км: {fnum(res['range_c'][0])}–{fnum(res['range_c'][1])} °C")
    if "emission" in res:
        lines.append("Фотоэффект: " + ("есть" if res["emission"] else "нет (энергии фотона не хватает)"))
    if "levels" in res:
        lines.append("Уровни: " + "; ".join(f"n={l['n']}: {fnum(l['energy_ev'])} эВ" for l in res["levels"]))
    if "points_mm" in res:
        lines.append("Отверстия (x, y), мм: " + "; ".join(f"({fnum(p['x'])}, {fnum(p['y'])})" for p in res["points_mm"]))
    if res.get("assumption"):
        lines.append("Допущение: " + res["assumption"])
    return "\n".join(lines)


ARG_LABELS = {"particle": "Частица", "n_levels": "Число уровней", "bolt_count": "Число отверстий",
              "driven_wheels": "Ведущих колёс"}
PARTICLE_RU = {"electron": "электрон", "proton": "протон", "neutron": "нейтрон"}


def _label(key: str, tool: str) -> str:
    if key in ARG_LABELS:
        return ARG_LABELS[key]
    spec = next((s for s in tools.SPECS if s["name"] == tool), None)
    if spec and key in spec["props"]:
        return spec["props"][key][1].split(" (")[0]
    return key


MODULE_OF = {"geology": 9, "quantum": 13, "cad": 6, "robotics": 12, "space": 8}


def route(text: str):
    """Подбирает расчёт. Возвращает {tool, args} или None (если чисел нет или правила не подошли)."""
    t = norm(text)
    for tool, triggers, extract in RULES:
        if not all(re.search(p, t) for p in triggers):
            continue
        args = extract(t)
        if args:
            return {"tool": tool, "args": args}
    return None


def answer(text: str):
    """Считает без ИИ. Возвращает {text, tool, module} или None."""
    r = route(text)
    if not r:
        return None
    tool, args = r["tool"], r["args"]
    res = tools.run(tool, args)
    given = "; ".join(f"{_label(k, tool)} = {PARTICLE_RU.get(v, fnum(v)) if isinstance(v, str) else fnum(v)}"
                      for k, v in args.items())
    if "error" in res:
        msg = res["error"]
        m = re.search(r"«(\w+)»", msg)
        need = _label(m.group(1), tool) if m else None
        if msg.startswith("не указан") and need:
            return {"text": f"Не хватает данных: {need}. Принято: {given}.", "tool": tool,
                    "module": _module(tool)}
        return {"text": f"Не могу посчитать: {msg}. Принято: {given}.", "tool": tool, "module": _module(tool)}
    return {"text": f"{format_result(tool, res)}\nПринято: {given}.", "tool": tool, "module": _module(tool)}


def _module(tool: str) -> int:
    if tool in ("space_ion_thruster", "space_hohmann", "space_rocket_delta_v"):
        return 15
    return MODULE_OF.get(tool.split("_")[0], 18)


CAPABILITIES = (
    "Без ИИ я умею:\n"
    "• считать: температуру и давление на глубине, буровой раствор, время бурения (геология); "
    "фотон, чёрное тело, де Бройль, яму, фотоэффект, E=mc², Карно (физика); диаметр вала, "
    "болтовую окружность; связь со спутником, орбиты, ракетное уравнение, ионный двигатель, "
    "перелёт по Гоману; шасси, батарею, вес бурильной колонны — например: "
    "«температура на глубине 5 км», «диаметр вала 11 кВт 1450 об/мин»;\n"
    "• «арбитраж» — котировки бирж;\n"
    "• память: «запомни …», «что ты помнишь»;\n"
    "• знания: «что ты знаешь о …» (по вашей базе знаний);\n"
    "• графики, разрез и панель во вкладках.\n"
    "Свободные рассуждения и разбор фото требуют ИИ."
)
