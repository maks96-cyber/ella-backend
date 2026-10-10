const express = require('express');
const cors = require('cors');
const path = require('path');
const { GoogleGenerativeAI } = require('@google/generative-ai');

const app = express();
app.use(cors());
app.use(express.json());

// Ваш бесплатный API-ключ Gemini
const GEMINI_API_KEY = "AQ.Ab8RN6KTpB21ayk05JaF_345lCLtrVz5YjCQVKHLZUTu8gLXCg";

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ 
  model: "gemini-1.5-flash",
  systemInstruction: "Ты — Элла, ассистент в стиле Джарвиса. Отвечай кратко, чётко и по делу."
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.post('/api/ask', async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) return res.status(400).json({ error: "Пустой запрос" });

    const prompt = `Пользователь спросил: "${query}". 
    Ответь коротко (1-2 предложения) и дай 3 ключевых шага или вывода.
    Верни строго в формате JSON:
    {
      "speech": "Короткий ответ для речи",
      "steps": ["Пункт 1", "Пункт 2", "Пункт 3"]
    }`;

    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: { responseMimeType: "application/json" }
    });

    const responseText = result.response.text();
    res.json(JSON.parse(responseText));

  } catch (error) {
    console.error(error);
    res.status(500).json({ 
      speech: "Ошибка связи с нейросетью Gemini.",
      steps: ["Проверьте API ключ", "Проверьте логи сервера"] 
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Ella ready with Gemini'));
