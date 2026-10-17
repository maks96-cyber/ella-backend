"""Модуль 6 — САПР (Компас-3D / SolidWorks).

Сервер на Render работает на Linux и НЕ может управлять Компасом напрямую
(Компас — Windows-программа с COM-интерфейсом). Поэтому схема такая:

  HUD / клиент --> POST /cad/jobs --> очередь на сервере
  kompas_bridge.py (на вашем ПК с Windows) сам забирает задания по HTTPS,
  выполняет их в Компасе и возвращает результат.

Безопасность: мост выполняет только заранее определённые действия
(ACTIONS) с проверенными параметрами — никакого произвольного кода.
Кроме того, сервер умеет сам генерировать DXF-чертежи (фланец, ступенчатый
вал), которые открываются в Компас-3D, SolidWorks и других САПР.
"""
import math
import os
import re
import threading
import time
import uuid

from calc_utils import num

LEASE_SECONDS = 120  # сколько мост «держит» задание до возврата в очередь
MAX_JOBS = 200
_lock = threading.Lock()
_jobs = {}

SAFE_NAME = re.compile(r"^[\w\-. ]{1,100}$", re.UNICODE)
OPEN_EXT = {".m3d", ".a3d", ".cdw", ".frw", ".dxf", ".stp", ".step"}
SAVE_EXT = {".pdf", ".stp", ".step", ".dxf", ".m3d", ".cdw"}


def _filename(params, allowed):
    name = str(params.get("filename", "")).strip()
    if not SAFE_NAME.match(name) or ".." in name:
        raise ValueError("filename: нужно только имя файла, без пути")
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed:
        raise ValueError(f"filename: допустимые расширения {', '.join(sorted(allowed))}")
    return {"filename": name}


# Белый список действий моста: имя -> валидатор параметров
ACTIONS = {
    "ping": lambda p: {},
    "open_file": lambda p: _filename(p, OPEN_EXT),
    "save_as": lambda p: _filename(p, SAVE_EXT),
}


# ---------- Очередь заданий ----------
def create_job(action, params):
    if action not in ACTIONS:
        raise ValueError(f"action: одно из {', '.join(ACTIONS)}")
    clean = ACTIONS[action](params if isinstance(params, dict) else {})
    job = {"id": uuid.uuid4().hex[:12], "action": action, "params": clean,
           "status": "pending", "created": int(time.time()),
           "lease_until": 0, "result": None}
    with _lock:
        if len(_jobs) >= MAX_JOBS:
            finished = [k for k, v in _jobs.items() if v["status"] in ("done", "error")]
            if not finished:
                raise ValueError("очередь заданий переполнена")
            del _jobs[min(finished, key=lambda k: _jobs[k]["created"])]
        _jobs[job["id"]] = job
    return _public(job)


def claim_next():
    """Для моста: выдаёт старейшее ожидающее задание."""
    now = time.time()
    with _lock:
        for job in _jobs.values():
            if job["status"] == "running" and job["lease_until"] < now:
                job["status"] = "pending"
        pending = [j for j in _jobs.values() if j["status"] == "pending"]
        if not pending:
            return None
        job = min(pending, key=lambda j: j["created"])
        job["status"] = "running"
        job["lease_until"] = now + LEASE_SECONDS
        return _public(job)


def post_result(job_id, ok, result):
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "running":
            raise ValueError("задание не найдено или не выполняется")
        job["status"] = "done" if ok else "error"
        text = str(result)
        job["result"] = result if isinstance(result, dict) and len(text) < 4000 \
            else {"value": text[:1000]}
        return _public(job)


def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return _public(job) if job else None


def list_jobs(limit=20):
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)
        return [_public(j) for j in jobs[:limit]]


def _public(job):
    return {k: job[k] for k in ("id", "action", "params", "status", "created", "result")}


# ---------- Минимальный DXF-писатель (R12, без зависимостей) ----------
class _Dxf:
    LAYERS = {"CONTOUR": 7, "HOLES": 5, "CENTER": 1}  # цвета AutoCAD

    def __init__(self):
        self.ents = []

    def line(self, x1, y1, x2, y2, layer="CONTOUR"):
        self.ents.append(
            f"0\nLINE\n8\n{layer}\n10\n{x1:.4f}\n20\n{y1:.4f}\n30\n0.0\n"
            f"11\n{x2:.4f}\n21\n{y2:.4f}\n31\n0.0")

    def circle(self, x, y, r, layer="CONTOUR"):
        self.ents.append(
            f"0\nCIRCLE\n8\n{layer}\n10\n{x:.4f}\n20\n{y:.4f}\n30\n0.0\n40\n{r:.4f}")

    def render(self) -> str:
        layers = "\n".join(
            f"0\nLAYER\n2\n{n}\n70\n0\n62\n{c}\n6\nCONTINUOUS"
            for n, c in self.LAYERS.items())
        return (
            "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n0\nENDSEC\n"
            "0\nSECTION\n2\nTABLES\n"
            "0\nTABLE\n2\nLTYPE\n70\n1\n"
            "0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0\n"
            "0\nENDTAB\n"
            f"0\nTABLE\n2\nLAYER\n70\n{len(self.LAYERS)}\n{layers}\n0\nENDTAB\n"
            "0\nENDSEC\n"
            "0\nSECTION\n2\nENTITIES\n" + "\n".join(self.ents) + "\n0\nENDSEC\n0\nEOF\n"
        )


def _bolt_positions(circle_d, count, start_deg):
    r = circle_d / 2
    return [(r * math.cos(math.radians(start_deg + i * 360 / count)),
             r * math.sin(math.radians(start_deg + i * 360 / count)))
            for i in range(count)]


def gen_flange(p) -> str:
    """Фланец: наружный диаметр, отверстие, окружность и болтовые отверстия."""
    outer = num(p, "outer_d", lo=20, hi=2000)
    bore = num(p, "bore_d", lo=1, hi=outer - 1)
    bc = num(p, "bolt_circle_d", lo=1, hi=outer)
    count = int(num(p, "bolt_count", lo=2, hi=64))
    hole = num(p, "bolt_hole_d", lo=1, hi=200)
    start = num(p, "start_angle_deg", 90, -360, 360)

    if bc / 2 + hole / 2 >= outer / 2 or bc / 2 - hole / 2 <= bore / 2:
        raise ValueError("болтовые отверстия не помещаются между отверстием и краем")
    if bc * math.sin(math.pi / count) < hole + 1:
        raise ValueError("соседние болтовые отверстия пересекаются")

    d = _Dxf()
    d.circle(0, 0, outer / 2)
    d.circle(0, 0, bore / 2)
    d.circle(0, 0, bc / 2, "CENTER")
    ext = outer / 2 + 5
    d.line(-ext, 0, ext, 0, "CENTER")
    d.line(0, -ext, 0, ext, "CENTER")
    for x, y in _bolt_positions(bc, count, start):
        d.circle(x, y, hole / 2, "HOLES")
    return d.render()


def gen_shaft(p) -> str:
    """Ступенчатый вал (вид сбоку): steps = [{"d": диаметр, "l": длина}, ...]."""
    steps = p.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
        raise ValueError("steps: список из 1-12 ступеней вида {\"d\":..,\"l\":..}")
    d = _Dxf()
    x, prev = 0.0, None
    for i, st in enumerate(steps, 1):
        if not isinstance(st, dict):
            raise ValueError(f"ступень {i}: нужен объект с полями d и l")
        r = num(st, "d", lo=1, hi=1000) / 2
        length = num(st, "l", lo=1, hi=5000)
        d.line(x, r, x + length, r)
        d.line(x, -r, x + length, -r)
        if prev is None:
            d.line(x, -r, x, r)
        else:
            d.line(x, prev, x, r)
            d.line(x, -prev, x, -r)
        x += length
        prev = r
    d.line(x, -prev, x, prev)
    d.line(-5, 0, x + 5, 0, "CENTER")
    return d.render()


GENERATORS = {
    "flange": (gen_flange, "outer_d, bore_d, bolt_circle_d, bolt_count, bolt_hole_d, [start_angle_deg]"),
    "shaft": (gen_shaft, "steps: [{d, l}, ...] (мм)"),
}


# ---------- Инженерные расчёты ----------
def shaft_diameter(p):
    """Минимальный диаметр вала по кручению: d = (16·T / (π·τ))^(1/3)."""
    if "torque_nm" in p:
        torque = num(p, "torque_nm", lo=0.001, hi=1e7)
    else:
        power = num(p, "power_kw", lo=0.001, hi=1e5)
        rpm = num(p, "rpm", lo=1, hi=1e5)
        torque = 9550 * power / rpm
    tau = num(p, "allowable_shear_mpa", 30, 5, 200)
    d = (16 * torque * 1000 / (math.pi * tau)) ** (1 / 3)
    return {
        "torque_nm": round(torque, 2),
        "d_min_mm": round(d, 2),
        "d_round_up_mm": math.ceil(d),
        "assumption": "только кручение; изгиб, усталость, шпоночный паз и запас "
                      "прочности проверяйте отдельно (обычно диаметр увеличивают).",
    }


def bolt_pattern(p):
    """Координаты болтовых отверстий на окружности."""
    bc = num(p, "bolt_circle_d", lo=1, hi=5000)
    count = int(num(p, "bolt_count", lo=1, hi=200))
    start = num(p, "start_angle_deg", 90, -360, 360)
    pts = _bolt_positions(bc, count, start)
    return {"points_mm": [{"x": round(x, 3), "y": round(y, 3)} for x, y in pts]}


CALCS = {
    "shaft_diameter": (shaft_diameter, "torque_nm ИЛИ (power_kw, rpm), [allowable_shear_mpa]"),
    "bolt_pattern": (bolt_pattern, "bolt_circle_d, bolt_count, [start_angle_deg]"),
}
