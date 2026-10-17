"""Общие помощники для расчётных модулей."""
import math

_MISSING = object()


def num(params: dict, key: str, default=_MISSING, lo=None, hi=None) -> float:
    """Читает число из params, проверяет диапазон. ValueError — для клиента (400)."""
    if key not in params or params[key] in (None, ""):
        if default is _MISSING:
            raise ValueError(f"не указан параметр «{key}»")
        return default
    try:
        value = float(params[key])
    except (TypeError, ValueError):
        raise ValueError(f"параметр «{key}» должен быть числом")
    if not math.isfinite(value):
        raise ValueError(f"параметр «{key}» должен быть конечным числом")
    if lo is not None and value < lo:
        raise ValueError(f"«{key}» не может быть меньше {lo}")
    if hi is not None and value > hi:
        raise ValueError(f"«{key}» не может быть больше {hi}")
    return value
