const express = require('express');
const axios = require('axios');
const router = express.Router();

const API_URL = 'http://localhost:5000/api';

// Lấy danh sách từ khóa
router.get('/keywords', async (req, res) => {
  try {
    const response = await axios.get(`${API_URL}/keywords`);
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching keywords:', error.message);
    res.status(500).json({ error: 'Không thể lấy danh sách từ khóa' });
  }
});

// Thêm từ khóa mới
router.post('/keywords', async (req, res) => {
  try {
    const response = await axios.post(`${API_URL}/keywords`, {
      keyword: req.body.keyword
    });
    res.json(response.data);
  } catch (error) {
    console.error('Error adding keyword:', error.message);
    res.status(500).json({ error: 'Không thể thêm từ khóa' });
  }
});

// Xóa từ khóa
router.delete('/keywords/:keyword', async (req, res) => {
  try {
    const response = await axios.delete(`${API_URL}/keywords/${req.params.keyword}`);
    res.json(response.data);
  } catch (error) {
    console.error('Error deleting keyword:', error.message);
    res.status(500).json({ error: 'Không thể xóa từ khóa' });
  }
});

// Bắt đầu crawl cho từ khóa
router.post('/crawl', async (req, res) => {
  try {
    const response = await axios.post(`${API_URL}/crawl`, {
      keyword: req.body.keyword
    });
    res.json(response.data);
  } catch (error) {
    console.error('Error starting crawl:', error.message);
    res.status(500).json({ error: 'Không thể bắt đầu crawl' });
  }
});

// Lấy bài báo theo từ khóa
router.get('/articles', async (req, res) => {
  try {
    const response = await axios.get(`${API_URL}/articles`, {
      params: {
        keyword: req.query.keyword,
        source: req.query.source
      }
    });
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching articles:', error.message);
    res.status(500).json({ error: 'Không thể lấy bài báo' });
  }
});

// Lấy báo cáo hàng ngày
router.get('/daily-report', async (req, res) => {
  try {
    const response = await axios.get(`${API_URL}/daily-report`, {
      params: {
        keyword: req.query.keyword
      }
    });
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching daily report:', error.message);
    res.status(500).json({ error: 'Không thể lấy báo cáo hàng ngày' });
  }
});

module.exports = router;