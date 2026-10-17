"""Инструменты для ИИ: Gemini и Claude вызывают наши расчёты вместо «прикидок».

Один список SPECS — два формата (Gemini и Claude). ИИ сам решает, когда
вызвать инструмент; результат возвращается ему, и он отвечает по цифрам.
Инструменты только считают и читают публичные котировки — ничего не пишут.
"""
import arbitrage
import cad
import geology
import quantum

N, I, S = "number", "integer", "string"


def _spec(name, desc, props, required, fn):
    return {"name": name, "description": desc, "props": props,
            "required": required, "fn": fn}


def _arbitrage(args):
    raw = str(args.get("assets", ""))
    assets = [a.strip() for a in raw.split(",") if a.strip()] or None
    return arbitrage.scan(assets)


SPECS = [
    # ----- Модуль 9: геология -----
    _spec("geology_thermal",
          "Температура горных пород на глубине (линейный градиент).",
          {"depth_km": (N, "Глубина, км (0-20)"),
           "surface_temp_c": (N, "Температура на поверхности, °C (по умолчанию 15)"),
           "gradient_c_per_km": (N, "Градиент, °C/км (по умолчанию 30)")},
          ["depth_km"], geology.thermal),
    _spec("geology_pressure",
          "Литостатическое и гидростатическое давление на глубине, МПа.",
          {"depth_km": (N, "Глубина, км"),
           "rock_density_kg_m3": (N, "Плотность породы, кг/м3 (по умолчанию 2700)"),
           "water_density_kg_m3": (N, "Плотность воды, кг/м3 (по умолчанию 1000)"),
           "pore_pressure_mpa": (N, "Поровое давление, МПа (необязательно)")},
          ["depth_km"], geology.pressure),
    _spec("geology_drilling_mud",
          "Давление бурового раствора на глубине и запас до порового давления и давления разрыва.",
          {"depth_km": (N, "Глубина, км"),
           "mud_density_kg_m3": (N, "Плотность раствора, кг/м3 (по умолчанию 1200)"),
           "pore_pressure_mpa": (N, "Поровое давление, МПа"),
           "fracture_pressure_mpa": (N, "Давление разрыва пласта, МПа")},
          ["depth_km"], geology.drilling_mud),
    _spec("geology_drill_time",
          "Время бурения до глубины по скорости проходки, с заменой долот.",
          {"depth_km": (N, "Глубина, км"),
           "rop_m_per_h": (N, "Скорость проходки, м/ч (по умолчанию 5)"),
           "bit_life_h": (N, "Ресурс долота, ч (по умолчанию 60)"),
           "trip_hours_per_bit": (N, "Часы на спуск-подъём за долото (по умолчанию 24)")},
          ["depth_km"], geology.drill_time),
    _spec("geology_geothermal_power",
          "Тепловая и электрическая мощность геотермального потока воды.",
          {"flow_kg_s": (N, "Расход, кг/с"),
           "delta_t_c": (N, "Перепад температуры, °C"),
           "efficiency": (N, "КПД преобразования в электричество (по умолчанию 0.10)")},
          ["flow_kg_s", "delta_t_c"], geology.geothermal_power),
    # ----- Модуль 13: квантовая физика и энергетика -----
    _spec("quantum_photon",
          "Энергия, частота, длина волны и импульс фотона (формула Планка).",
          {"wavelength_nm": (N, "Длина волны, нм"),
           "frequency_hz": (N, "Частота, Гц (вместо длины волны)")},
          [], quantum.photon),
    _spec("quantum_blackbody",
          "Излучение абсолютно чёрного тела: пик по Вину, мощность по Стефану-Больцману, закон Планка.",
          {"temperature_k": (N, "Температура, К"),
           "wavelength_nm": (N, "Длина волны для спектральной яркости, нм (необязательно)")},
          ["temperature_k"], quantum.blackbody),
    _spec("quantum_de_broglie",
          "Длина волны де Бройля частицы.",
          {"velocity_m_s": (N, "Скорость, м/с"),
           "particle": (S, "electron, proton или neutron"),
           "mass_kg": (N, "Масса, кг (если не указана частица)")},
          ["velocity_m_s"], quantum.de_broglie),
    _spec("quantum_box",
          "Уровни энергии частицы в бесконечной потенциальной яме, эВ.",
          {"length_nm": (N, "Ширина ямы, нм"),
           "n_levels": (I, "Сколько уровней вывести (1-20, по умолчанию 3)"),
           "particle": (S, "electron, proton или neutron (по умолчанию electron)")},
          ["length_nm"], quantum.box),
    _spec("quantum_photoelectric",
          "Фотоэффект: максимальная кинетическая энергия электронов и порог.",
          {"wavelength_nm": (N, "Длина волны света, нм"),
           "work_function_ev": (N, "Работа выхода, эВ")},
          ["wavelength_nm", "work_function_ev"], quantum.photoelectric),
    _spec("quantum_mass_energy",
          "Энергия покоя массы по E = m c^2, в джоулях и кВт·ч.",
          {"mass_kg": (N, "Масса, кг")},
          ["mass_kg"], quantum.mass_energy),
    _spec("quantum_carnot",
          "Предельный КПД тепловой машины по Карно.",
          {"t_hot_k": (N, "Температура нагревателя, К"),
           "t_cold_k": (N, "Температура холодильника, К")},
          ["t_hot_k", "t_cold_k"], quantum.carnot),
    # ----- Модуль 6: САПР / инженерия -----
    _spec("cad_shaft_diameter",
          "Минимальный диаметр вала по кручению (по моменту или по мощности и оборотам).",
          {"torque_nm": (N, "Крутящий момент, Н·м"),
           "power_kw": (N, "Мощность, кВт (вместо момента)"),
           "rpm": (N, "Обороты, об/мин (вместе с мощностью)"),
           "allowable_shear_mpa": (N, "Допускаемое касательное напряжение, МПа (по умолчанию 30)")},
          [], cad.shaft_diameter),
    _spec("cad_bolt_pattern",
          "Координаты болтовых отверстий на окружности, мм.",
          {"bolt_circle_d": (N, "Диаметр окружности центров, мм"),
           "bolt_count": (I, "Количество отверстий"),
           "start_angle_deg": (N, "Начальный угол, градусы (по умолчанию 90)")},
          ["bolt_circle_d", "bolt_count"], cad.bolt_pattern),
    # ----- Модуль 7: котировки -----
    _spec("arbitrage_scan",
          "Текущие цены и спреды между биржами Binance, Kraken, Coinbase (только чтение, не торговля).",
          {"assets": (S, "Список через запятую: BTC, ETH, SOL (по умолчанию все)")},
          [], _arbitrage),
]

_BY_NAME = {s["name"]: s for s in SPECS}


def run(name, args):
    """Выполняет инструмент. Ошибки возвращаем ИИ как данные, а не падаем."""
    spec = _BY_NAME.get(name)
    if not spec:
        return {"error": f"неизвестный инструмент {name}"}
    if not isinstance(args, dict):
        args = {}
    try:
        return spec["fn"](args)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # сеть, внешние сервисы
        return {"error": f"сбой инструмента: {e}"}


def _props(spec, upper):
    return {k: {"type": t.upper() if upper else t, "description": d}
            for k, (t, d) in spec["props"].items()}


def _schema(spec, upper):
    schema = {"type": "OBJECT" if upper else "object", "properties": _props(spec, upper)}
    if spec["required"]:
        schema["required"] = spec["required"]
    return schema


GEMINI_TOOLS = [{"functionDeclarations": [
    {"name": s["name"], "description": s["description"], "parameters": _schema(s, True)}
    for s in SPECS]}]

CLAUDE_TOOLS = [
    {"name": s["name"], "description": s["description"], "input_schema": _schema(s, False)}
    for s in SPECS]
