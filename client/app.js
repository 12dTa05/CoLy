const express = require('express');
const path = require('path');
const axios = require('axios');

const app = express();
const PORT = 3000;
const API_BASE_URL = 'http://localhost:5000/api';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/', async (req, res) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/keywords`);
    const keywords = response.data.keywords || [];
    res.render('index', { keywords });
  } catch (error) {
    console.error('Error fetching keywords:', error.message);
    res.render('index', { keywords: [], error: 'Không thể tải danh sách từ khóa' });
  }
});

app.post('/add-keyword', async (req, res) => {
  const { keyword } = req.body;
  try {
    await axios.post(`${API_BASE_URL}/keywords`, { keyword });
    res.redirect('/');
  } catch (error) {
    console.error('Error adding keyword:', error.message);
    res.redirect('/?error=Không thể thêm từ khóa');
  }
});

app.post('/delete-keyword', async (req, res) => {
  const { keyword } = req.body;
  try {
    await axios.delete(`${API_BASE_URL}/keywords/${keyword}`);
    res.redirect('/');
  } catch (error) {
    console.error('Error deleting keyword:', error.message);
    res.redirect('/?error=Không thể xóa từ khóa');
  }
});

app.get('/articles', async (req, res) => {
  const { keyword } = req.query;
  try {
    const response = await axios.get(`${API_BASE_URL}/articles`, {
      params: { keyword }
    });
    const articles = response.data.articles || [];
    const keywordsResponse = await axios.get(`${API_BASE_URL}/keywords`);
    const keywords = keywordsResponse.data.keywords || [];
    res.render('articles', { articles, keyword, keywords });
  } catch (error) {
    console.error('Error fetching articles:', error.message);
    res.render('articles', { articles: [], keyword, keywords: [], error: 'Không thể tải bài báo' });
  }
});

app.post('/start-crawl', async (req, res) => {
  const { keyword } = req.body;
  try {
    await axios.post(`${API_BASE_URL}/crawl`, { keyword });
    res.redirect(`/articles?keyword=${keyword}`);
  } catch (error) {
    console.error('Error starting crawl:', error.message);
    res.redirect(`/articles?keyword=${keyword}&error=Không thể bắt đầu crawl`);
  }
});

app.listen(PORT, () => {
  console.log(`Client server running on http://localhost:${PORT}`);
});