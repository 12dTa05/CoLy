const express = require('express');
const path = require('path');
const axios = require('axios');
const session = require('express-session');

const app = express();
const PORT = 3000;
const API_BASE_URL = 'http://localhost:5000/api';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(session({
  secret: 'your-secret-key-change-in-production',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false, maxAge: 24 * 60 * 60 * 1000 } // 24 giờ
}));

// Middleware kiểm tra đăng nhập
const isAuthenticated = (req, res, next) => {
  if (req.session.token) {
    return next();
  }
  res.redirect('/login');
};

// Trang đăng nhập
app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

// Xử lý đăng nhập
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/login`, { username, password });
    req.session.token = response.data.access_token;
    req.session.username = response.data.username;
    res.redirect('/');
  } catch (error) {
    console.error('Error logging in:', error.response?.data?.error || error.message);
    res.render('login', { error: 'Tên đăng nhập hoặc mật khẩu không đúng' });
  }
});

// Trang đăng ký
app.get('/register', (req, res) => {
  res.render('register', { error: null });
});

// Xử lý đăng ký
app.post('/register', async (req, res) => {
  const { username, email, password, confirmPassword } = req.body;
  
  if (password !== confirmPassword) {
    return res.render('register', { error: 'Mật khẩu xác nhận không khớp' });
  }
  
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/register`, { username, email, password });
    req.session.token = response.data.access_token;
    res.redirect('/');
  } catch (error) {
    console.error('Error registering:', error.response?.data?.error || error.message);
    res.render('register', { error: error.response?.data?.error || 'Lỗi đăng ký' });
  }
});

// Đăng xuất
app.get('/', isAuthenticated, async (req, res) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/keywords`, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    
    res.render('index', { 
      keywords: response.data.keywords || [], 
      username: req.session.username,
      keywordId: null  // Quan trọng: thêm biến này để sử dụng trong navigation
    });
  } catch (error) {
    console.error('Error fetching keywords:', error.response?.data?.error || error.message);
    if (error.response?.status === 401) {
      return res.redirect('/login');
    }
    res.render('index', { 
      keywords: [], 
      username: req.session.username, 
      keywordId: null,  // Quan trọng: thêm biến này để sử dụng trong navigation
      error: 'Không thể tải danh sách từ khóa' 
    });
  }
});

// Thêm từ khóa mới
app.post('/add-keyword', isAuthenticated, async (req, res) => {
  const { keyword } = req.body;
  try {
    await axios.post(`${API_BASE_URL}/keywords`, { keyword }, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    res.redirect('/');
  } catch (error) {
    console.error('Error adding keyword:', error.response?.data?.error || error.message);
    res.redirect('/?error=Không thể thêm từ khóa');
  }
});

// Xóa từ khóa
app.post('/delete-keyword', isAuthenticated, async (req, res) => {
  const { keywordId } = req.body;
  try {
    await axios.delete(`${API_BASE_URL}/keywords/${keywordId}`, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    res.redirect('/');
  } catch (error) {
    console.error('Error deleting keyword:', error.response?.data?.error || error.message);
    res.redirect('/?error=Không thể xóa từ khóa');
  }
});

// Danh sách bài báo theo từ khóa
app.get('/articles', isAuthenticated, async (req, res) => {
  const { keywordId } = req.query;
  try {
    // Lấy danh sách từ khóa
    const keywordsResponse = await axios.get(`${API_BASE_URL}/keywords`, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    const keywords = keywordsResponse.data.keywords || [];
    
    if (!keywordId && keywords.length > 0) {
      // Nếu không có keywordId, chọn từ khóa đầu tiên
      return res.redirect(`/articles?keywordId=${keywords[0].id}`);
    }
    
    if (!keywordId) {
      return res.render('articles', { 
        articles: [], 
        keywords, 
        keyword: '', 
        keywordId: null, 
        username: req.session.username 
      });
    }
    
    // Lấy danh sách bài báo cho từ khóa
    const articlesResponse = await axios.get(`${API_BASE_URL}/articles`, {
      params: { keyword_id: keywordId },
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    
    res.render('articles', { 
      articles: articlesResponse.data.articles || [], 
      keywords, 
      keyword: articlesResponse.data.keyword, 
      keywordId, 
      username: req.session.username 
    });
    
  } catch (error) {
    console.error('Error fetching articles:', error.response?.data?.error || error.message);
    if (error.response?.status === 401) {
      return res.redirect('/login');
    }
    res.render('articles', { 
      articles: [], 
      keywords: [], 
      keyword: '', 
      keywordId: keywordId || null, 
      username: req.session.username,
      error: 'Không thể tải danh sách bài báo' 
    });
  }
});

// Bắt đầu crawl
app.post('/start-crawl', isAuthenticated, async (req, res) => {
  const { keywordId } = req.body;
  try {
    await axios.post(`${API_BASE_URL}/crawl`, { keyword_id: keywordId }, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    res.redirect(`/articles?keywordId=${keywordId}`);
  } catch (error) {
    console.error('Error starting crawl:', error.response?.data?.error || error.message);
    res.redirect(`/articles?keywordId=${keywordId}&error=Không thể bắt đầu crawl`);
  }
});

app.listen(PORT, () => {
  console.log(`Client server running on http://localhost:${PORT}`);
});

// Trang xem danh sách bài tổng hợp theo từ khóa
app.get('/summaries', isAuthenticated, async (req, res) => {
  const { keywordId } = req.query;
  try {
    // Lấy thông tin từ khóa
    const keywordResponse = await axios.get(`${API_BASE_URL}/keywords`, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    const keywords = keywordResponse.data.keywords || [];
    
    if (!keywordId) {
      return res.render('summaries', { 
        summaries: [], 
        keywords, 
        selectedKeyword: null, 
        keywordId: null,  // Thêm biến này để sử dụng trong navigation
        username: req.session.username
      });
    }
    
    // Lấy danh sách bài tổng hợp
    const summariesResponse = await axios.get(`${API_BASE_URL}/summaries`, {
      params: { keyword_id: keywordId },
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    
    const summaries = summariesResponse.data.summaries || [];
    const selectedKeyword = keywords.find(k => k.id === keywordId);
    
    res.render('summaries', { 
      summaries, 
      keywords, 
      selectedKeyword,
      keywordId,  // Thêm biến này để sử dụng trong navigation
      username: req.session.username
    });
    
  } catch (error) {
    console.error('Error fetching summaries:', error.response?.data?.error || error.message);
    if (error.response?.status === 401) {
      return res.redirect('/login');
    }
    res.render('summaries', { 
      summaries: [], 
      keywords: [], 
      selectedKeyword: null,
      keywordId: keywordId || null,  // Thêm biến này để sử dụng trong navigation
      username: req.session.username,
      error: 'Không thể tải danh sách bài tổng hợp' 
    });
  }
});

// Trang xem chi tiết bài tổng hợp
app.get('/summaries/:summaryId', isAuthenticated, async (req, res) => {
  const { summaryId } = req.params;
  try {
    const response = await axios.get(`${API_BASE_URL}/summaries/${summaryId}`, {
      headers: { Authorization: `Bearer ${req.session.token}` }
    });
    
    const summary = response.data;
    
    res.render('summary-detail', { 
      summary, 
      keywordId: summary.keyword_id,  // Thêm biến này để sử dụng trong navigation
      username: req.session.username
    });
    
  } catch (error) {
    console.error('Error fetching summary detail:', error.response?.data?.error || error.message);
    if (error.response?.status === 401) {
      return res.redirect('/login');
    }
    res.render('summary-detail', { 
      summary: null, 
      keywordId: null,  // Thêm biến này để sử dụng trong navigation
      username: req.session.username,
      error: 'Không thể tải chi tiết bài tổng hợp' 
    });
  }
});

// Tạo lại bài tổng hợp
app.post('/regenerate-summary', isAuthenticated, async (req, res) => {
  const { keywordId, date } = req.body;
  try {
    await axios.post(`${API_BASE_URL}/summaries/regenerate`, 
      { keyword_id: keywordId, date },
      { headers: { Authorization: `Bearer ${req.session.token}` }}
    );
    
    res.redirect(`/summaries?keywordId=${keywordId}`);
    
  } catch (error) {
    console.error('Error regenerating summary:', error.response?.data?.error || error.message);
    res.redirect(`/summaries?keywordId=${keywordId}&error=Không thể tạo lại bài tổng hợp`);
  }
});