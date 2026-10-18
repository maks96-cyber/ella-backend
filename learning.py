import os
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI(title="Ella AI Assistant - Learning Module")

# Модель входящей команды на обучение
class LearnRequest(BaseModel):
    topic: str
    depth: str = "standard"  # standard или deep

# Хранилище изученных знаний Эллы (в продакшене лучше использовать векторную БД, например FAISS, ChromaDB или PostgreSQL)
KNOWLEDGE_BASE = {}

def research_and_learn_task(topic: str):
    """
    Фоновый процесс: Элла ищет информацию, анализирует и сохраняет в память.
    """
    print(f"[Ella Learning System]: Начинаю самостоятельное изучение темы: {topic}")
    
    # 1. Формирование плана изучения
    learning_plan = [
        f"Определение и ключевые понятия {topic}",
        f"Как работает {topic} и основные принципы",
        f"Практическое применение и примеры {topic}"
    ]
    
    learned_data = []
    
    # 2. Имитация сбора и анализа данных (здесь подключается сбор через API или Search)
    for step in learning_plan:
        print(f"[Ella Learning System]: Изучаю раздел: {step}")
        # Запрос к LLM для генерации глубинного анализа по разделу
        # В реальном коде отправляем запрос в Gemini API / OpenAI API
        content = f"Выжимка знаний по разделу '{step}': базовые принципы и ключевые структуры изучены."
        learned_data.append({"section": step, "content": content})
    
    # 3. Сохранение результатов в базу знаний Эллы
    KNOWLEDGE_BASE[topic.lower()] = {
        "status": "completed",
        "summary": f"Тема '{topic}' успешно изучена и структурирована.",
        "details": learned_data
    }
    print(f"[Ella Learning System]: Изучение темы '{topic}' завершено!")

@app.post("/api/ella/learn")
async def start_learning(request: LearnRequest, background_tasks: BackgroundTasks):
    """
    Эндпоинт для отправки команды Элле на обучение.
    Выполняется в фоновом режиме, чтобы не блокировать голосовой ответ.
    """
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Укажите тему для изучения.")
    
    # Запуск изучения в фоновом режиме
    background_tasks.add_task(research_and_learn_task, topic)
    
    return {
        "status": "accepted",
        "message": f"Принято! Начинаю самостоятельное изучение темы: '{topic}'. Я сообщу, когда закончу."
    }

@app.get("/api/ella/knowledge")
async def get_knowledge(topic: str):
    """
    Проверка изученных Эллой знаний.
    """
    data = KNOWLEDGE_BASE.get(topic.lower())
    if not data:
        return {"status": "not_found", "message": f"Тема '{topic}' еще не была изучена."}
    return data
