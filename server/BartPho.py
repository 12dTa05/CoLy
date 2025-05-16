import re
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import google.generativeai as genai

class BartphoSummarizer:
    def __init__(self):
        """Khởi tạo mô hình BARTpho để tóm tắt văn bản tiếng Việt"""
        self.tokenizer = None
        self.model = None
        
    def load_model(self):
        """Tải mô hình khi cần thiết để tiết kiệm bộ nhớ"""
        if self.model is None:
            self.tokenizer = AutoTokenizer.from_pretrained("vinai/bartpho-word")
            self.model = AutoModelForSeq2SeqLM.from_pretrained("vinai/bartpho-word")
            
            # Đặt mô hình lên GPU nếu có
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = self.model.to(device)
            
    def vietnamese_tokenize(self, text):
        """Tách câu tiếng Việt dựa trên dấu câu và quy tắc đặc thù"""
        if not text:
            return []
            
        # Tiền xử lý - giữ nguyên dấu chấm trong số thập phân và viết tắt
        text = re.sub(r'(\d+)\.(\d+)', r'\1<dot>\2', text)
        text = re.sub(r'([A-Za-z])\.([A-Za-z])', r'\1<dot>\2', text)
        
        # Tách câu dựa trên các dấu câu kết thúc
        text = re.sub(r'([.!?;])\s+', r'\1\n', text)
        text = re.sub(r'([.!?;])\"', r'\1\"\n', text)
        text = re.sub(r'\.\.\.\s*', '...\n', text)
        
        # Xử lý một số trường hợp đặc biệt trong tiếng Việt
        text = re.sub(r'\n-\s+', '\n', text)  # Loại bỏ dấu gạch đầu dòng sau khi tách câu
        
        # Khôi phục dấu chấm trong số thập phân và viết tắt
        text = text.replace('<dot>', '.')
        
        # Tách các câu và loại bỏ khoảng trắng thừa
        sentences = [s.strip() for s in text.split('\n') if s.strip()]
        
        return sentences

    def summarize(self, text, max_length=512):
        """Tóm tắt văn bản sử dụng BARTpho"""
        self.load_model()
        
        # Tokenize và tạo inputs
        inputs = self.tokenizer(text, max_length=1024, truncation=True, return_tensors="pt")
        
        # Đưa lên cùng thiết bị với mô hình
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Tạo tóm tắt
        summary_ids = self.model.generate(
            inputs["input_ids"],
            max_length=max_length,
            min_length=50,
            num_beams=4,
            early_stopping=True
        )
        
        # Giải mã tóm tắt
        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary
        
    def generate_title(self, keyword, article_summaries):
        """Tạo tiêu đề dựa trên BARTpho"""
        if not article_summaries:
            return f"Tổng hợp tin tức về {keyword}"
        
        try:
            # Kết hợp tóm tắt các bài báo
            combined_summaries = "\n\n".join(article_summaries[:5])  # Tối đa 5 bài
            
            # Tạo prompt yêu cầu tiêu đề
            prompt = f"Các bài báo sau đây nói về chủ đề '{keyword}':\n\n{combined_summaries}\n\nTạo một tiêu đề ngắn gọn, thu hút cho bài tổng hợp tin tức này:"
            
            # Sử dụng BARTpho để tạo tiêu đề
            title = self.summarize(prompt, max_length=50)
            
            # Làm sạch tiêu đề
            title = title.strip().split("\n")[0]  # Lấy dòng đầu tiên
            
            return title
        except Exception as e:
            print(f"Lỗi khi tạo tiêu đề: {e}")
            return f"Tổng hợp tin tức về {keyword}"
            
    def summarize_with_references(self, keyword, all_articles):
        """Tổng hợp bài báo với tham chiếu đến nguồn gốc"""
        # Chuẩn bị dữ liệu
        article_summaries = []
        source_mapping = {}
        article_sources = set()
        article_ids = []
        
        # Thu thập thông tin từ các bài báo
        for i, article in enumerate(all_articles):
            article_ids.append(article['_id'])
            article_sources.add(article['source'])
            
            if article.get('summary'):
                article_summaries.append(article.get('summary', ''))
            
            # Lưu source mapping
            source_mapping[str(i+1)] = {
                'url': article['real_link'],
                'title': article['title'],
                'source': article['source']
            }
        
        if not article_summaries:
            return f"# Tổng hợp tin tức về {keyword}\n\nKhông có đủ bài báo để tổng hợp.", article_ids, list(article_sources), source_mapping
        
        # Kết hợp nội dung của các bài báo
        combined_content = "\n\n".join([f"Bài {i+1}: {summary}" for i, summary in enumerate(article_summaries)])
        
        # Tạo prompt cho BARTpho
        prompt = f"Tổng hợp các bài báo sau về chủ đề '{keyword}':\n\n{combined_content}"
        
        # Sử dụng BARTpho để tạo bản tổng hợp
        raw_summary = self.summarize(prompt)
        
        # Thêm tham chiếu vào bản tổng hợp
        sentences = self.vietnamese_tokenize(raw_summary)
        sentences_with_refs = []
        
        # Tạo danh sách các cụm từ nhận dạng từ mỗi bài
        article_identifiers = []
        for i, summary in enumerate(article_summaries):
            # Lấy các cụm từ đặc trưng từ mỗi bài
            words = summary.lower().split()
            phrases = [' '.join(words[j:j+3]) for j in range(len(words)-2) if j+2 < len(words)]
            article_identifiers.append((i+1, phrases[:10] if len(phrases) >= 10 else phrases))  # Lấy tối đa 10 cụm từ
        
        # Thêm tham chiếu vào từng câu
        for sentence in sentences:
            # Tìm các bài báo phù hợp với câu này
            matching_articles = []
            for article_idx, phrases in article_identifiers:
                matches = sum(1 for phrase in phrases if phrase.lower() in sentence.lower())
                if matches >= 1:  # Nếu có ít nhất 1 cụm từ khớp
                    matching_articles.append(str(article_idx))
            
            # Thêm tham chiếu vào cuối câu
            if matching_articles:
                ref_str = ", ".join(sorted(matching_articles))
                sentences_with_refs.append(f"{sentence} [{ref_str}]")
            else:
                sentences_with_refs.append(sentence)
        
        # Kết hợp các câu đã có tham chiếu
        summary_with_refs = " ".join(sentences_with_refs)
        
        # Tạo tiêu đề
        title = self.generate_title(keyword, article_summaries)
        
        return summary_with_refs, title, article_ids, list(article_sources), source_mapping

class GeminiPolisher:
    def __init__(self, api_key=None):
        """Khởi tạo với API key cho Gemini"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "AIzaSyDKEnG-QYRkJzYpZd5ibmVswhAjtsnFOkU")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    def polish_and_structure(self, title, summary_with_refs, keyword):
        """Làm đẹp và cấu trúc bài tổng hợp với Gemini"""
        prompt = f"""Hãy cấu trúc lại và làm cho bài viết sau mạch lạc và chuyên nghiệp hơn như một bài báo tổng hợp.                 
                NỘI DUNG BÀI BÁO: {summary_with_refs}                
                QUY TẮC TUYỆT ĐỐI PHẢI TUÂN THỦ:
                1. PHẢI giữ nguyên tất cả các tham chiếu dạng [1], [2], [1, 2], ... xuất hiện ở cuối câu.
                2. KHÔNG xóa, thêm hoặc sửa đổi BẤT KỲ tham chiếu nào.
                3. PHẢI chia bài viết thành 3 phần chính: "Tóm tắt chính", "Thông tin chi tiết", và "Kết luận"
                4. Phần "Tóm tắt chính" nên chiếm khoảng 20% nội dung, "Thông tin chi tiết" khoảng 65%, và "Kết luận" khoảng 15%.
                5. CHỈ cải thiện cách viết, kết nối ý, làm nội dung mạch lạc hơn mà không thay đổi thông tin.
                6. Làm rõ thêm những điểm chưa rõ ràng từ tóm tắt ngắn gọn ban đầu.
                
                Kết quả cuối cùng PHẢI theo cấu trúc chính xác sau đây:
                ## Tóm tắt chính
                [nội dung tóm tắt]
                ## Thông tin chi tiết
                [nội dung chi tiết]
                ## Kết luận
                [nội dung kết luận]
            """
        
        response = self.model.generate_content(prompt)
        polished_content = response.text.strip()
        return polished_content