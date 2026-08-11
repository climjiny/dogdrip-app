import sys
import re
import urllib.parse
from bs4 import BeautifulSoup
import streamlit as st
import streamlit.components.v1 as components

# Page config for Mobile Responsive UI
st.set_page_config(
    page_title="개드립 열람기",
    page_icon="🐶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 크롬 우회 세션
try:
    from curl_cffi import requests as c_requests
except ImportError:
    import requests as c_requests

# ---------------------------------------------------------
# 백엔드 엔진 (사용자 원본 로직 100% 보존)
# ---------------------------------------------------------
class DogDripBackend:
    def __init__(self):
        self.articles = []
        self.current_page = 1
        
        if c_requests:
            if hasattr(c_requests, 'Session'):
                try:
                    self.session = c_requests.Session(impersonate="chrome120")
                except Exception:
                    self.session = c_requests.Session()
            else:
                self.session = c_requests
            
            if hasattr(self.session, 'headers'):
                self.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': 'https://www.dogdrip.net/'
                })
        else:
            self.session = None

    def fetch_articles(self, page=1, keyword=""):
        self.current_page = max(1, page)
        keyword = keyword.strip()
        self.articles.clear()

        try:
            if keyword:
                encoded_keyword = urllib.parse.quote(keyword)
                url = f"https://www.dogdrip.net/dogdrip?page={self.current_page}&search_target=title_content&search_keyword={encoded_keyword}"
            else:
                url = f"https://www.dogdrip.net/dogdrip?page={self.current_page}"

            if self.session:
                res = self.session.get(url, timeout=10, verify=False)
            else:
                import requests
                res = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select("div.ed.flex")
                if not items:
                    items = soup.select("table.bd_lst tbody tr, ul.bd_lst > li")

                for item in items:
                    badge = item.select_one("span.badge")
                    if badge and "인기" in badge.get_text():
                        continue

                    a_tag = item.select_one("a.title-link, a.title, a[data-document-srl]")
                    if not a_tag:
                        continue

                    href = a_tag.get('href', '')
                    if not re.search(r'/dogdrip/\d+', href) and 'data-document-srl' not in a_tag.attrs:
                        continue

                    clean_href = href.split('?')[0]
                    if clean_href.startswith('http'):
                        link = clean_href
                    else:
                        link = "https://www.dogdrip.net" + (clean_href if clean_href.startswith('/') else "/" + clean_href)

                    if any(art['link'] == link for art in self.articles):
                        continue

                    title_text = a_tag.get_text(strip=True)
                    if not title_text or len(title_text) < 2:
                        continue

                    title_clean = re.sub(r'\s+', ' ', title_text).strip()
                    if title_clean in ["개드립", "인기글", "목록", "다음", "이전", "글쓰기"]:
                        continue

                    self.articles.append({"title": title_clean, "link": link})

            return {"success": True, "articles": self.articles, "page": self.current_page}
        except Exception as e:
            return {"success": False, "error": str(e), "articles": [], "page": self.current_page}

    def fetch_article_detail(self, link):
        try:
            if self.session:
                res = self.session.get(link, timeout=10, verify=False)
            else:
                import requests
                res = requests.get(link, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.dogdrip.net/'
                })

            if res.status_code != 200:
                return {"success": False, "error": f"HTTP 오류 {res.status_code}"}

            soup = BeautifulSoup(res.text, 'html.parser')
            title_el = soup.select_one('h1.ed.title, div.document_title, h1, a.title')
            title_text = title_el.get_text(strip=True) if title_el else "게시글 상세"

            content_el = soup.select_one('div.ed.article-content, div.xe_content, div.read_body, article')
            comment_el = soup.select_one('#commentbox, div.comment-list, #cmtPosition, div.comment')

            body_html = ""
            if content_el:
                body_html += f"<div class='article-content-box'>{str(content_el)}</div>"
            else:
                body_html += "<p style='color:gray; padding:20px;'>본문 내용을 찾을 수 없습니다.</p>"

            if comment_el:
                for unneeded in comment_el.select('form, .comment-editor, .btn-area, .rhymix_comment_editor'):
                    unneeded.decompose()
                body_html += f"""
                <div class='comment-section-box'>
                    <h3 class='comment-section-header'>💬 댓글</h3>
                    {str(comment_el)}
                </div>
                """

            temp_soup = BeautifulSoup(body_html, 'html.parser')

            for tag in temp_soup.select('img, video, source, a, iframe'):
                for attr in ['src', 'poster', 'data-src', 'href']:
                    if tag.has_attr(attr):
                        val = tag[attr]
                        if val.startswith('//'):
                            tag[attr] = 'https:' + val
                        elif val.startswith('/'):
                            tag[attr] = 'https://www.dogdrip.net' + val

            for v in temp_soup.select('video'):
                v['controls'] = ''
                v['autoplay'] = ''
                v['loop'] = ''
                v['muted'] = ''
                v['playsinline'] = ''
                v['preload'] = 'auto'
                
                src_val = v.get('src', '')
                if src_val:
                    if src_val.startswith('//'):
                        src_val = 'https:' + src_val
                    elif src_val.startswith('/'):
                        src_val = 'https://www.dogdrip.net' + src_val
                    v['src'] = src_val
                    if not temp_soup.select('source'):
                        source_tag = temp_soup.new_tag('source', src=src_val, type='video/mp4')
                        v.append(source_tag)

            clean_body_html = str(temp_soup)

            full_html = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta name="referrer" content="no-referrer">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        padding: 10px;
                        color: #1e293b;
                        line-height: 1.6;
                        background: #ffffff;
                    }}
                    .article-title {{
                        font-size: 18px;
                        font-weight: 800;
                        color: #0f172a;
                        margin-bottom: 12px;
                        padding-bottom: 8px;
                        border-bottom: 2px solid #e2e8f0;
                    }}
                    img, video {{
                        max-width: 100% !important;
                        height: auto !important;
                        display: block;
                        margin: 12px auto;
                        border-radius: 8px;
                    }}
                    iframe {{
                        max-width: 100%;
                        width: 100%;
                        min-height: 250px;
                        border: none;
                    }}
                    .comment-section-box {{
                        margin-top: 25px;
                        padding-top: 15px;
                        border-top: 2px dashed #cbd5e1;
                    }}
                    .comment-section-header {{
                        font-size: 16px;
                        font-weight: 800;
                        color: #1e40af;
                        margin-bottom: 12px;
                    }}
                    .comment-item {{
                        padding: 8px 12px;
                        margin-bottom: 8px;
                        border: 1px solid #f1f5f9;
                        border-radius: 6px;
                        background: #f8fafc;
                        font-size: 13px;
                    }}
                    a {{ color: #2563eb; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="article-title">{title_text}</div>
                <div class="article-body">{clean_body_html}</div>
            </body>
            </html>
            """
            return {"success": True, "html": full_html, "link": link}
        except Exception as e:
            return {"success": False, "error": str(e), "html": f"<h3>로드 오류</h3><p>{e}</p>"}

# ---------------------------------------------------------
# Streamlit 모바일 전용 프론트엔드 UI
# ---------------------------------------------------------
@st.cache_resource
def get_backend():
    return DogDripBackend()

backend = get_backend()

# Session State 초기화
if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_article" not in st.session_state:
    st.session_state.selected_article = None

st.title("🐶 개드립 모바일 열람기")

# 1. 상단 컨트롤 바 (검색 및 새로고침)
col_search, col_btn1, col_btn2 = st.columns([3, 1, 1])
with col_search:
    keyword = st.text_input("검색어", placeholder="검색어 입력 후 엔터", label_visibility="collapsed")
with col_btn1:
    if st.button("🔍 검색", use_container_width=True):
        st.session_state.page = 1
        st.session_state.selected_article = None
with col_btn2:
    if st.button("🔄 새로고침", use_container_width=True):
        st.session_state.selected_article = None
        st.rerun()

# 2. 본문 보기 화면 (게시글이 선택된 경우)
if st.session_state.selected_article:
    if st.button("⬅️ 목록으로 돌아가기", type="primary", use_container_width=True):
        st.session_state.selected_article = None
        st.rerun()

    with st.spinner("본문 및 댓글 로딩 중..."):
        detail = backend.fetch_article_detail(st.session_state.selected_article)
        if detail["success"]:
            # HTML을 높이에 맞게 렌더링
            components.html(detail["html"], height=1000, scrolling=True)
            st.markdown(f"[🌐 브라우저에서 원본 보기]({detail['link']})")
        else:
            st.error(f"오류 발생: {detail['error']}")

# 3. 게시글 목록 화면 (선택된 게시글이 없을 때)
else:
    with st.spinner(f"페이지 {st.session_state.page} 데이터 수집 중..."):
        res = backend.fetch_articles(page=st.session_state.page, keyword=keyword)

    if res["success"] and res["articles"]:
        st.caption(f"📄 현재 {st.session_state.page} 페이지 (총 {len(res['articles'])}개 게시글)")
        
        # 목록 출력 (버튼 클릭 시 해당 글 선택)
        for art in res["articles"]:
            if st.button(art["title"], key=art["link"], use_container_width=True):
                st.session_state.selected_article = art["link"]
                st.rerun()

        # 페이지네이션
        st.divider()
        col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
        with col_p1:
            if st.button("◀ 이전", disabled=(st.session_state.page <= 1), use_container_width=True):
                st.session_state.page -= 1
                st.rerun()
        with col_p2:
            st.markdown(f"<h4 style='text-align: center;'>{st.session_state.page} Page</h4>", unsafe_allow_html=True)
        with col_p3:
            if st.button("다음 ▶", use_container_width=True):
                st.session_state.page += 1
                st.rerun()
    else:
        st.warning("게시글을 불러올 수 없거나 검색 결과가 없습니다.")
