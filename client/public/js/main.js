document.addEventListener('DOMContentLoaded', function() {
    // Các phần tử DOM
    const keywordForm = document.getElementById('keyword-form');
    const keywordInput = document.getElementById('keyword');
    const keywordList = document.getElementById('keyword-list');
    const crawlForm = document.getElementById('crawl-form');
    const crawlKeywordSelect = document.getElementById('crawl-keyword');
    const crawlStatus = document.getElementById('crawl-status');
    const articleKeywordSelect = document.getElementById('article-keyword');
    const articleSourceSelect = document.getElementById('article-source');
    const fetchArticlesBtn = document.getElementById('fetch-articles');
    const articlesContainer = document.getElementById('articles-container');
    const noArticlesDiv = document.getElementById('no-articles');
    const reportKeywordSelect = document.getElementById('report-keyword');
    const fetchReportBtn = document.getElementById('fetch-report');
    const reportContainer = document.getElementById('report-container');
  
    // Tải danh sách từ khóa
    async function loadKeywords() {
      try {
        const response = await fetch('/api/keywords');
        const data = await response.json();
        
        if (data.keywords && Array.isArray(data.keywords)) {
          updateKeywordLists(data.keywords);
        }
      } catch (error) {
        console.error('Error loading keywords:', error);
        alert('Không thể tải danh sách từ khóa. Hãy kiểm tra console để biết thêm chi tiết.');
      }
    }
  
    // Cập nhật tất cả danh sách từ khóa
    function updateKeywordLists(keywords) {
      // Cập nhật danh sách từ khóa
      keywordList.innerHTML = '';
      if (keywords.length === 0) {
        keywordList.innerHTML = '<li class="list-group-item">Chưa có từ khóa nào.</li>';
      } else {
        keywords.forEach(keyword => {
          const li = document.createElement('li');
          li.className = 'list-group-item keyword-item';
          li.innerHTML = `
            <span>${keyword}</span>
            <button class="btn btn-sm btn-danger delete-keyword" data-keyword="${keyword}">Xóa</button>
          `;
          keywordList.appendChild(li);
        });
      }
  
      // Cập nhật select cho crawl
      crawlKeywordSelect.innerHTML = '';
      keywords.forEach(keyword => {
        const option = document.createElement('option');
        option.value = keyword;
        option.textContent = keyword;
        crawlKeywordSelect.appendChild(option);
      });
  
      // Cập nhật select cho xem bài báo
      articleKeywordSelect.innerHTML = '';
      keywords.forEach(keyword => {
        const option = document.createElement('option');
        option.value = keyword;
        option.textContent = keyword;
        articleKeywordSelect.appendChild(option);
      });
  
      // Cập nhật select cho báo cáo
      reportKeywordSelect.innerHTML = '';
      keywords.forEach(keyword => {
        const option = document.createElement('option');
        option.value = keyword;
        option.textContent = keyword;
        reportKeywordSelect.appendChild(option);
      });
    }
  
    // Thêm từ khóa mới
    keywordForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      const keyword = keywordInput.value.trim();
      
      if (!keyword) {
        alert('Vui lòng nhập từ khóa.');
        return;
      }
  
      try {
        const response = await fetch('/api/keywords', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ keyword })
        });
        
        const data = await response.json();
        
        if (data.message) {
          keywordInput.value = '';
          loadKeywords();
        } else if (data.error) {
          alert(`Lỗi: ${data.error}`);
        }
      } catch (error) {
        console.error('Error adding keyword:', error);
        alert('Không thể thêm từ khóa. Hãy kiểm tra console để biết thêm chi tiết.');
      }
    });
  
    // Xóa từ khóa
    keywordList.addEventListener('click', async function(e) {
      if (e.target.classList.contains('delete-keyword')) {
        const keyword = e.target.getAttribute('data-keyword');
        
        if (confirm(`Bạn có chắc chắn muốn xóa từ khóa "${keyword}"?`)) {
          try {
            const response = await fetch(`/api/keywords/${keyword}`, {
              method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.message) {
              loadKeywords();
            } else if (data.error) {
              alert(`Lỗi: ${data.error}`);
            }
          } catch (error) {
            console.error('Error deleting keyword:', error);
            alert('Không thể xóa từ khóa. Hãy kiểm tra console để biết thêm chi tiết.');
          }
        }
      }
    });
  
    // Bắt đầu crawl
    crawlForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      const keyword = crawlKeywordSelect.value;
      
      if (!keyword) {
        alert('Vui lòng chọn từ khóa để crawl.');
        return;
      }
  
      try {
        crawlStatus.innerHTML = `
          <div class="d-flex align-items-center">
            <div class="spinner-border" role="status"></div>
            <span>Đang bắt đầu crawl cho từ khóa "${keyword}"...</span>
          </div>
        `;
        
        const response = await fetch('/api/crawl', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ keyword })
        });
        
        const data = await response.json();
        
        if (data.message) {
          crawlStatus.innerHTML = `
            <div class="alert alert-success">
              ${data.message}
            </div>
          `;
        } else if (data.error) {
          crawlStatus.innerHTML = `
            <div class="alert alert-danger">
              Lỗi: ${data.error}
            </div>
          `;
        }
      } catch (error) {
        console.error('Error starting crawl:', error);
        crawlStatus.innerHTML = `
          <div class="alert alert-danger">
            Không thể bắt đầu crawl. Hãy kiểm tra console để biết thêm chi tiết.
          </div>
        `;
      }
    });
  
    // Tải bài báo
    fetchArticlesBtn.addEventListener('click', async function() {
      const keyword = articleKeywordSelect.value;
      const source = articleSourceSelect.value;
      
      if (!keyword) {
        alert('Vui lòng chọn từ khóa.');
        return;
      }
  
      try {
        articlesContainer.innerHTML = `
          <div class="col-12 text-center py-4">
            <div class="spinner-border" role="status" style="width: 3rem; height: 3rem;"></div>
            <p class="mt-2">Đang tải bài báo...</p>
          </div>
        `;
        
        const url = new URL('/api/articles', window.location.origin);
        url.searchParams.append('keyword', keyword);
        if (source) {
          url.searchParams.append('source', source);
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.articles && Array.isArray(data.articles)) {
          if (data.articles.length === 0) {
            articlesContainer.innerHTML = '';
            noArticlesDiv.classList.remove('d-none');
          } else {
            noArticlesDiv.classList.add('d-none');
            renderArticles(data.articles);
          }
        } else if (data.error) {
          articlesContainer.innerHTML = `
            <div class="col-12">
              <div class="alert alert-danger">
                Lỗi: ${data.error}
              </div>
            </div>
          `;
        }
      } catch (error) {
        console.error('Error fetching articles:', error);
        articlesContainer.innerHTML = `
          <div class="col-12">
            <div class="alert alert-danger">
              Không thể tải bài báo. Hãy kiểm tra console để biết thêm chi tiết.
            </div>
          </div>
        `;
      }
    });
  
    // Hiển thị bài báo
    function renderArticles(articles) {
      articlesContainer.innerHTML = '';
      
      articles.forEach(article => {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4 mb-4';
        
        const sourceIcon = getSourceIcon(article.source);
        const formattedDate = formatDate(article.pub_date || article.crawled_at);
        
        col.innerHTML = `
          <div class="card article-card">
            <div class="card-header d-flex justify-content-between align-items-center">
              <div>${sourceIcon} ${article.source}</div>
              <small>${formattedDate}</small>
            </div>
            <div class="card-body">
              <h5 class="card-title">${article.title}</h5>
              <p class="card-text">${article.description || 'Không có mô tả.'}</p>
              ${article.summary ? `<div class="summary-text"><strong>Tóm tắt:</strong> ${article.summary}</div>` : ''}
              <a href="${article.link}" target="_blank" class="btn btn-primary mt-3">Đọc bài viết</a>
            </div>
          </div>
        `;
        
        articlesContainer.appendChild(col);
      });
    }
  
    // Lấy biểu tượng cho nguồn
    function getSourceIcon(source) {
      switch (source) {
        case 'vnexpress':
          return '<span class="badge bg-primary">VnExpress</span>';
        case 'dantri':
          return '<span class="badge bg-success">Dân Trí</span>';
        case 'tuoitre':
          return '<span class="badge bg-danger">Tuổi Trẻ</span>';
        case 'thanhnien':
          return '<span class="badge bg-warning text-dark">Thanh Niên</span>';
        default:
          return '<span class="badge bg-secondary">Khác</span>';
      }
    }
  
    // Định dạng ngày
    function formatDate(dateString) {
      if (!dateString) return 'N/A';
      
      try {
        const date = new Date(dateString);
        return date.toLocaleString('vi-VN');
      } catch (error) {
        return dateString;
      }
    }
  
    // Tải báo cáo hàng ngày
    fetchReportBtn.addEventListener('click', async function() {
      const keyword = reportKeywordSelect.value;
      
      if (!keyword) {
        alert('Vui lòng chọn từ khóa.');
        return;
      }
  
      try {
        reportContainer.innerHTML = `
          <div class="text-center py-4">
            <div class="spinner-border" role="status" style="width: 3rem; height: 3rem;"></div>
            <p class="mt-2">Đang tải báo cáo...</p>
          </div>
        `;
        
        const url = new URL('/api/daily-report', window.location.origin);
        url.searchParams.append('keyword', keyword);
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
          reportContainer.innerHTML = `
            <div class="alert alert-danger">
              Lỗi: ${data.error}
            </div>
          `;
          return;
        }
        
        // Hiển thị báo cáo
        renderReport(data);
      } catch (error) {
        console.error('Error fetching report:', error);
        reportContainer.innerHTML = `
          <div class="alert alert-danger">
            Không thể tải báo cáo. Hãy kiểm tra console để biết thêm chi tiết.
          </div>
        `;
      }
    });
  
    // Hiển thị báo cáo
    function renderReport(report) {
      const formattedDate = formatDate(report.date);
      
      let html = `
        <div class="mb-4">
          <h3>Báo cáo hàng ngày: ${report.keyword}</h3>
          <p><strong>Ngày:</strong> ${formattedDate}</p>
          <p><strong>Tổng số bài báo:</strong> ${report.total_articles}</p>
        </div>
      `;
      
      if (report.articles && report.articles.length > 0) {
        html += `<h4>Danh sách bài báo:</h4>`;
        
        // Nhóm bài báo theo nguồn
        const groupedArticles = {};
        report.articles.forEach(article => {
          if (!groupedArticles[article.source]) {
            groupedArticles[article.source] = [];
          }
          groupedArticles[article.source].push(article);
        });
        
        // Hiển thị bài báo theo nhóm
        Object.keys(groupedArticles).forEach(source => {
          const sourceIcon = getSourceIcon(source);
          html += `
            <div class="card mb-3">
              <div class="card-header">
                ${sourceIcon} ${source} (${groupedArticles[source].length} bài)
              </div>
              <div class="card-body">
                <div class="list-group">
          `;
          
          groupedArticles[source].forEach(article => {
            html += `
              <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                  <div>
                    <h5><a href="${article.link}" target="_blank">${article.title}</a></h5>
                    <p>${article.description || 'Không có mô tả.'}</p>
                    ${article.summary ? `<div class="summary-text"><strong>Tóm tắt:</strong> ${article.summary}</div>` : ''}
                  </div>
                </div>
              </div>
            `;
          });
          
          html += `
                </div>
              </div>
            </div>
          `;
        });
      } else {
        html += `<div class="alert alert-info">Không có bài báo nào cho ngày hôm nay.</div>`;
      }
      
      reportContainer.innerHTML = html;
    }
  
    // Tải danh sách từ khóa khi trang được tải
    loadKeywords();
  });