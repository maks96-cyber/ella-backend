"""Мост Элла <-> КОМПАС-3D. Запускать на ПК с Windows, где установлен Компас.

Установка:   pip install requests pywin32
Переменные:  ELLA_URL         адрес бэкенда (по умолчанию ваш Render)
             ELLA_HMAC_SECRET тот же секрет, что на Render
             ELLA_WORKDIR     папка с чертежами/моделями (по умолчанию C:\\Ella\\cad)
Запуск:      python kompas_bridge.py

Мост сам подключается к серверу (входящие порты открывать не нужно), берёт
задания и выполняет ТОЛЬКО действия из белого списка: ping, open_file, save_as.
Файлы читаются и пишутся только внутри ELLA_WORKDIR.

ВАЖНО: COM-вызовы ниже написаны по документации API7 Компаса, но не проверялись
на вашей версии. Если какой-то вызов не сработает, мост вернёт текст ошибки
в задание — по нему легко поправить обработчик.
"""
import hashlib
import hmac
import os
import re
import time
import uuid

import requests

BASE_URL = os.getenv("ELLA_URL", "https://ella-backend-yq1s.onrender.com").rstrip("/")
SECRET = os.environ["ELLA_HMAC_SECRET"].encode()
WORKDIR = os.path.abspath(os.getenv("ELLA_WORKDIR", r"C:\Ella\cad"))
POLL_SECONDS = 3
SAFE_NAME = re.compile(r"^[\w\-. ]{1,100}$", re.UNICODE)


# ---------- Подпись запросов (тот же алгоритм, что на сервере) ----------
def _sign(method, path, ts, nonce, body: bytes) -> str:
    msg = "\n".join([method.upper(), path, str(ts), nonce,
                     hashlib.sha256(body).hexdigest()]).encode()
    return hmac.new(SECRET, msg, hashlib.sha256).hexdigest()


def call(method, path, payload=None):
    import json
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b""
    ts, nonce = int(time.time()), uuid.uuid4().hex
    headers = {"X-Ella-Timestamp": str(ts), "X-Ella-Nonce": nonce,
               "X-Ella-Signature": _sign(method, path, ts, nonce, body),
               "Content-Type": "application/json"}
    r = requests.request(method, BASE_URL + path, data=body, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------- Работа с Компасом ----------
def kompas_app():
    import pythoncom
    from win32com.client import Dispatch
    pythoncom.CoInitialize()
    app = Dispatch("Kompas.Application.7")
    app.Visible = True
    return app


def safe_path(filename: str) -> str:
    if not SAFE_NAME.match(filename) or ".." in filename:
        raise ValueError("недопустимое имя файла")
    path = os.path.abspath(os.path.join(WORKDIR, filename))
    if os.path.commonpath([WORKDIR, path]) != WORKDIR:
        raise ValueError("файл вне рабочей папки")
    return path


def do_ping(params):
    app = kompas_app()
    info = {"connected": True, "workdir": WORKDIR}
    try:
        info["documents_open"] = app.Documents.Count
    except Exception as e:  # свойство может отличаться в версии Компаса
        info["documents_note"] = f"не удалось получить: {e}"
    return info


def do_open_file(params):
    path = safe_path(params["filename"])
    if not os.path.isfile(path):
        raise FileNotFoundError(f"нет файла {params['filename']} в рабочей папке")
    app = kompas_app()
    app.Documents.Open(path, True, False)  # путь, видимость, только чтение
    return {"opened": params["filename"]}


def do_save_as(params):
    path = safe_path(params["filename"])
    os.makedirs(WORKDIR, exist_ok=True)
    app = kompas_app()
    doc = app.ActiveDocument
    if doc is None:
        raise RuntimeError("нет активного документа")
    doc.SaveAs(path)
    return {"saved": params["filename"]}


HANDLERS = {"ping": do_ping, "open_file": do_open_file, "save_as": do_save_as}


def run_job(job):
    handler = HANDLERS.get(job["action"])
    if not handler:
        return False, {"error": f"действие {job['action']} не поддерживается мостом"}
    try:
        return True, handler(job.get("params", {}))
    except Exception as e:
        return False, {"error": f"{type(e).__name__}: {e}"}


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    print(f"Мост запущен. Сервер: {BASE_URL}, папка: {WORKDIR}")
    while True:
        try:
            job = call("GET", "/cad/bridge/next").get("job")
            if job:
                print("Задание:", job["id"], job["action"])
                ok, result = run_job(job)
                call("POST", f"/cad/bridge/result/{job['id']}",
                     {"ok": ok, "result": result})
                print("  ->", "готово" if ok else f"ошибка: {result}")
                continue  # сразу проверяем следующее
        except Exception as e:
            print("Связь с сервером:", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
