import re
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import google.generativeai as genai

class BartphoSummarizer: #bartpho tóm tắt
    def __init__(self):
        self.tokenizer = None
        self.model = None
        
    def load_model(self):
        if self.model is None:
            self.tokenizer = AutoTokenizer.from_pretrained("vinai/bartpho-word")
            self.model = AutoModelForSeq2SeqLM.from_pretrained("vinai/bartpho-word")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = self.model.to(device)
            
    def vietnamese_tokenize(self, text): #tách đoạn thành các câu
        if not text:
            return []

        text = re.sub(r'(\d+)\.(\d+)', r'\1<dot>\2', text)
        text = re.sub(r'([A-Za-z])\.([A-Za-z])', r'\1<dot>\2', text)

        text = re.sub(r'([.!?;])\s+', r'\1\n', text)
        text = re.sub(r'([.!?;])\"', r'\1\"\n', text)
        text = re.sub(r'\.\.\.\s*', '...\n', text)

        text = re.sub(r'\n-\s+', '\n', text)  #loại bỏ dấu gạch đầu dòng 
        
        text = text.replace('<dot>', '.')

        sentences = [s.strip() for s in text.split('\n') if s.strip()]
        
        return sentences

    def summarize(self, text, max_length=512):
        self.load_model()

        inputs = self.tokenizer(text, max_length=1024, truncation=True, return_tensors="pt")

        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        summary_ids = self.model.generate(
            inputs["input_ids"],
            max_length=max_length,
            min_length=50,
            num_beams=4,
            early_stopping=True
        )

        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary
        
    def generate_title(self, keyword, article_summaries):
        if not article_summaries:
            return f"Tổng hợp tin tức về {keyword}"
        
        try:
            combined_summaries = "\n\n".join(article_summaries)

            prompt = f"Các bài báo sau đây nói về chủ đề '{keyword}':\n\n{combined_summaries}\n\nTạo một tiêu đề ngắn gọn, thu hút cho bài tổng hợp tin tức này:"
            title = self.summarize(prompt, max_length=50)

            title = title.strip().split("\n")[0]  # Lấy dòng đầu tiên
            
            return title
        except Exception as e:
            print(f"Lỗi khi tạo tiêu đề: {e}")
            return ""
            
    def summarize_with_references(self, keyword, all_articles):
        article_summaries = []
        source_mapping = {}
        article_sources = set()
        article_ids = []
        
        for i, article in enumerate(all_articles):
            article_ids.append(article['_id'])
            article_sources.add(article['source'])
            
            if article.get('content'):
                article_summaries.append(article.get('content', ''))
            
            #lưu source mapping
            source_mapping[str(i+1)] = {
                'url': article['real_link'],
                'title': article['title'],
                'source': article['source']
            }
        
        if not article_summaries:
            return f"{keyword}Không có đủ bài báo để tổng hợp.", article_ids, list(article_sources), source_mapping
        
        combined_content = "\n\n".join([f"Bài {i+1}: {content}" for i, content in enumerate(article_summaries)])

        prompt = f"Tổng hợp các bài báo sau về chủ đề '{keyword}':\n\n{combined_content}"
        raw_summary = self.summarize(prompt)
        
        #thêm tham chiếu vào tổng hợp
        sentences = self.vietnamese_tokenize(raw_summary)
        sentences_with_refs = []
        
        #tạo danh sách các cụm từ nhận dạng từ mỗi bài
        article_identifiers = []
        for i, summary in enumerate(article_summaries):
            #lấy các cụm từ đặc trưng từ mỗi bài
            words = summary.lower().split()
            phrases = [' '.join(words[j:j+3]) for j in range(len(words)-2) if j+2 < len(words)]
            article_identifiers.append((i+1, phrases[:10] if len(phrases) >= 10 else phrases))
        
        #thêm tham chiếu vào từng câu
        for sentence in sentences:
            matching_articles = []
            for article_idx, phrases in article_identifiers:
                if any(phrase.lower() in sentence.lower() for phrase in phrases):
                    matching_articles.append(str(article_idx))
            
            #thêm tham chiếu vào cuối câu
            if matching_articles:
                ref_str = ", ".join(sorted(matching_articles)[:3])
                sentences_with_refs.append(f"{sentence} [{ref_str}]")
            else:
                sentences_with_refs.append(sentence)
        
        #kết hợp các câu
        summary_with_refs = " ".join(sentences_with_refs)
        
        title = self.generate_title(keyword, article_summaries)
        
        return summary_with_refs, title, article_ids, list(article_sources), source_mapping

class GeminiPolisher:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "AIzaSyDKEnG-QYRkJzYpZd5ibmVswhAjtsnFOkU")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    def polish_and_structure(self, title, summary_with_refs, keyword):
        prompt = f"""Hãy cấu trúc lại và làm cho bài viết sau mạch lạc và chuyên nghiệp hơn như một bài báo tổng hợp.                 
            NỘI DUNG BÀI BÁO: {summary_with_refs}                
            QUY TẮC TUYỆT ĐỐI PHẢI TUÂN THỦ:
            1. PHẢI giữ nguyên tất cả các tham chiếu dạng [1], [2], [1, 2], ... xuất hiện ở cuối câu.
            2. KHÔNG đặt tham chiếu ở cuối đoạn văn, mà hãy đặt tham chiếu cho từng câu cụ thể.
            3. PHẢI làm chi tiết hơn và mở rộng nội dung từ tóm tắt ban đầu.
            4. PHẢI đảm bảo bao quát nhiều chủ đề CNTT khác nhau, không chỉ giới hạn ở 1-2 chủ đề.
            5. PHẢI chia bài viết thành 4-5 phần chính, bao gồm "Tóm tắt chính", các phần thông tin chi tiết về các chủ đề khác nhau, và "Kết luận"
            6. Phần "Tóm tắt chính" nên chiếm khoảng 15% nội dung, các phần thông tin chi tiết khoảng 75%, và "Kết luận" khoảng 10%.
            7. CHỈ cải thiện cách viết, kết nối ý, làm nội dung mạch lạc hơn mà không thay đổi thông tin.

            Kết quả cuối cùng PHẢI theo cấu trúc chính xác sau đây, không thêm bất kì phần trả lời nào khác:
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