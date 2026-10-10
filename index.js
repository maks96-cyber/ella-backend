const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

// Отдаем HTML интерфейс
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.post('/api/ask', (req, res) => {
  const { query } = req.body;
  res.json({
    speech: `Принято. Анализирую запрос: ${query || 'без запроса'}. Вот ключевые шаги.`,
    steps: [
      "1. Проверить уровень риска (не более 2-5% от депозита)",
      "2. Убедиться в наличии защитных ордеров (стоп-лосс)",
      "3. Оценить тренд перед совершением сделки"
    ]
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Ella server active'));
