import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import chromadb

app = FastAPI(title="Ella AI Assistant - Vector Memory System")

# Инициализация локальной векторной базы данных ChromaDB
# База сохраняет данные в папку ./ella_vector_db на сервере
chroma_client = chromadb.PersistentClient(path="./ella_vector_db")

# Создаем или подключаем коллекцию знаний Эллы
# ChromaDB автоматически векторизует текст с помощью встроенных моделей
collection = chroma_client.get_or_create_collection(name="ella_mega_memory")

class LearnRequest(BaseModel):
    topic: str

class QueryRequest(BaseModel):
    question: str

def background_vectorize_knowledge(topic: str):
    """
    Фоновый процесс: Элла собирает информацию, разбивает ее на фрагменты (чанги) 
    и записывает векторы в ChromaDB. Здесь можно загружать хоть миллионы страниц!
    """
    print(f"[Ella Vector Memory]: Начинаю глубокое изучение и индексацию темы: {topic}")
    
    # Имитация генерации / сбора большого массива данных (в реальном проекте здесь парсинг или вызов LLM)
    simulated_deep_docs = [
        f"Фундаментальные основы {topic}: ключевые принципы, история развития и базовые концепции.",
        f"Техническая архитектура {topic}: устройство внутренних компонентов, алгоритмы и структура данных.",
        f"Практическая реализация {topic}: лучшие практики, оптимизация производительности, примеры кода.",
        f"Решение сложных проблем и краевые случаи в {topic}: как справляться с ошибками и масштабировать систему."
    ]
    
    # Уникальные ID для каждого фрагмента знаний
    doc_ids = [f"{topic.lower()}_chunk_{i}" for i in range(len(simulated_deep_docs))]
    metadatas = [{"topic": topic, "part": i} for i in range(len(simulated_deep_docs))]
    
    # Сохраняем векторы в базу
    collection.add(
        documents=simulated_deep_docs,
        metadatas=metadatas,
        ids=doc_ids
    )
    print(f"[Ella Vector Memory]: Успешно проиндексировано и сохранено в память блоков для темы: {topic}")

@app.post("/api/ella/learn")
async def start_learning(request: LearnRequest, background_tasks: BackgroundTasks):
    """
    Команда Элле на самостоятельное изучение темы и сохранение в векторную память.
    """
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Укажите тему для изучения.")
    
    # Запуск процесса в фоне, чтобы не вешать сервер
    background_tasks.add_task(background_vectorize_knowledge, topic)
    
    return {
        "status": "accepted",
        "message": f"Принято! Элла начала самостоятельное изучение и векторизацию темы: '{topic}'. Память расширяется."
    }

@app.post("/api/ella/ask")
async def query_memory(request: QueryRequest):
    """
    Семантический поиск по миллионам записей Эллы. 
    Находит наиболее точные фрагменты знаний по смыслу вопроса.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Запрос пуст.")
    
    # Поиск топ-3 самых релевантных фрагментов в векторной базе
    results = collection.query(
        query_texts=[question],
        n_results=3
    )
    
    if not results or not results['documents'][0]:
        return {
            "status": "not_found",
            "answer": "В моей текущей векторной памяти нет информации по этому вопросу. Дай команду изучить эту тему."
        }
    
    return {
        "status": "success",
        "query": question,
        "retrieved_knowledge": results['documents'][0],
        "metadata": results['metadatas'][0]
    }
