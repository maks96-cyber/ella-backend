const express = require('express');
const cors = require('cors');
const app = express();
app.use(cors());
app.use(express.json());

app.post('/api/ask', (req, res) => {
  const { query } = req.body;
  res.json({
    speech: `Анализ по запросу "${query || 'биржа'}" готов.`,
    steps: [
      "1. Риск не более 5% от депозита",
      "2. Стоп-лосс 1.5%",
      "3. Работа только с ликвидными активами"
    ]
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Ella server active'));
