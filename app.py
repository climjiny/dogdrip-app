import sys
import re
import urllib.parse
from bs4 import BeautifulSoup
import streamlit as st
import streamlit.components.v1 as components

# Page config
st.set_page_config(
    page_title="개드립 모바일 열람기",
    page_icon="🐶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 크롬 우회 세션
try:
    from curl_cffi import requests as c_requests
except ImportError:
    import requests as c_requests

# 📌 CSS 스타일: 모바일 레이아웃 고정 및 워터마크/메뉴 숨기기
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
    div[data-testid="stDecoration"] {visibility: hidden; height: 0%; position: fixed;}
    div[data-testid="stStatusWidget"] {visibility: hidden; height: 0%; position: fixed;}
    
    div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 4px !important; }
    div[data-testid="stHorizontalBlock"] > div { flex: 1 1 0% !important; min-width: 0 !important; }
    div[data-testid="stHorizontalBlock"] button { padding: 4px 0px !important; font-size: 14px !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 백엔드 엔진
# ---------------------------------------------------------
class DogDripBackend:
    def __init__(self):
        self.session = c_requests.Session(impersonate="chrome120") if c_requests else None
        if self.session:
            self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

    def fetch_articles(self, page=1, keyword=""):
        # (기존 fetch_articles 코드 유지)
        self.current_page = max(1, page)
        keyword = keyword.strip()
        articles_list = []
        try:
            url = f"https://www.dogdrip.net/dogdrip?page={self.current_page}" + (f"&search_target=title_content&search_keyword={urllib.parse.quote(keyword)}" if keyword else "")
            res = self.session.get(url, timeout=10, verify=False) if self.session else None
            if res and res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select("div.ed.flex, table.bd_lst tbody tr, ul.bd_lst > li")
                for item in items:
                    a_tag = item.select_one("a.title-link, a.title, a[data-document-srl]")
                    if not a_tag or "인기" in (item.select_one("span.badge") or "").get_text("", strip=True): continue
                    href = a_tag.get('href', '')
                    if not (re.search(r'/dogdrip/\d+', href) or 'data-document-srl' in a_tag.attrs): continue
                    link = href if href.startswith('http') else "https://www.dogdrip.net" + href
                    if not any(art['link'] == link for art in articles_list):
                        title = re.sub(r'\s+', ' ', a_tag.get_text(strip=True)).strip()
                        if title and title not in ["개드립", "인기글", "목록", "다음", "이전", "글쓰기"]:
                            articles_list.append({"title": title, "link": link})
            return {"success": True, "articles": articles_list, "page": self.current_page}
        except: return {"success": False, "articles": [], "page": self.current_page}

    def fetch_article_detail(self, link, fallback_title=""):
        try:
            res = self.session.get(link, timeout=10, verify=False)
            soup = BeautifulSoup(res.text, 'html.parser')
            content_el = soup.select_one('div.ed.article-content, div.xe_content, div.read_body, article')
            
            # 📌 수정: 댓글 중복 방지 (고유 ID 기반으로 Set 사용)
            comment_el = soup.select_one('#commentbox, div.comment-list, #cmtPosition, div.comment, #comment, div.xe_comment')
            rebuilt_comments_html = ""
            if comment_el:
                seen_ids = set()
                rebuilt_comments_html = '<div class="comment-section-box"><h3>💬 댓글</h3>'
                # 고유한 댓글 ID를 가진 요소만 선택
                items = comment_el.select('div[id^="comment_"], li[id^="comment_"]')
                for cmt in items:
                    c_id = cmt.get('id')
                    if c_id and c_id not in seen_ids:
                        seen_ids.add(c_id)
                        # (댓글 렌더링 로직 유지...)
                        author = cmt.select_one('.nick, .author').get_text(strip=True) if cmt.select_one('.nick, .author') else "익명"
                        content = cmt.select_one('.xe_content, .comment-body')
                        rebuilt_comments_html += f'<div style="padding:10px; border-bottom:1px solid #eee;"><strong>{author}</strong><br>{content}</div>'
                rebuilt_comments_html += '</div>'

            # (위쪽 HTML 템플릿 영역에 double tap 감지 로직 적용)
            # ... [하단 자바스크립트 부분 수정] ...
            full_html = f"""
            ... (생략: 위 코드와 동일하되 아래 JS 부분만 수정)
            """
            return {"success": True, "html": full_html.replace("300", "200"), "link": link} # 200ms로 민감도 조정
        except Exception as e: return {"success": False, "error": str(e)}

# ---------------------------------------------------------
# UI 부분 (생략...)
# ---------------------------------------------------------
# (기존과 동일하되, 위 로직들을 반영하여 전체 실행하세요)
