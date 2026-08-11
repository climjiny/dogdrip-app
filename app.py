import sys
import re
import urllib.parse
from bs4 import BeautifulSoup
import streamlit as st
import streamlit.components.v1 as components

# Page config
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
# 백엔드 엔진
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
        articles_list = []

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

                    if any(art['link'] == link for art in articles_list):
                        continue

                    title_text = a_tag.get_text(strip=True)
                    if not title_text or len(title_text) < 2:
                        continue

                    title_clean = re.sub(r'\s+', ' ', title_text).strip()
                    if title_clean in ["개드립", "인기글", "목록", "다음", "이전", "글쓰기"]:
                        continue

                    articles_list.append({"title": title_clean, "link": link})

            return {"success": True, "articles": articles_list, "page": self.current_page}
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
                for unneeded in comment_el.select('form, .comment-editor, .btn-area, .rhymix_comment_editor, .vote, .voted_count, .vote_area'):
                    unneeded.decompose()

                for el in comment_el.select('.number, .num, .vote-count, .vote'):
                    el.decompose()

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

            # 📌 [요청 반영] "게시글 상세" 아래, 본문 시작점 바로 위에 제목 배치
            full_html = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta name="referrer" content="no-referrer">
                <style>
                    html, body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        padding: 0;
                        margin: 0;
                        color: #1e293b;
                        line-height: 1.5;
                        background: #ffffff;
                    }}
                    .detail-header-label {{
                        font-size: 13px;
                        font-weight: 700;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    .article-title-box {{
                        font-size: 18px;
                        font-weight: 800;
                        color: #0f172a;
                        margin-bottom: 16px;
                        padding-bottom: 10px;
                        border-bottom: 2px solid #e2e8f0;
                        word-break: keep-all;
                        line-height: 1.4;
                    }}
                    img, video {{
                        max-width: 100% !important;
                        height: auto !important;
                        display: block;
                        margin: 10px auto;
                        border-radius: 8px;
                    }}
                    iframe {{
                        max-width: 100%;
                        width: 100%;
                        min-height: 250px;
                        border: none;
                    }}
                    .comment-section-box {{
                        margin-top: 15px;
                        padding-top: 10px;
                        border-top: 2px dashed #cbd5e1;
                    }}
                    .comment-section-header {{
                        font-size: 15px;
                        font-weight: 800;
                        color: #1e40af;
                        margin-bottom: 8px;
                    }}
                    .comment-item, div[id^="comment_"] {{
                        padding: 4px 8px !important;
                        margin-bottom: 4px !important;
                        border: 1px solid #f1f5f9;
                        border-radius: 4px;
                        background: #f8fafc;
                        font-size: 12.5px !important;
                        line-height: 1.3 !important;
                    }}
                    .vote, .voted_count, .vote_area, .vote-count {{
                        display: none !important;
                    }}
                    a {{ color: #2563eb; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="detail-header-label">게시글 상세</div>
                <div class="article-title-box">{title_text}</div>
                <div class="article-body">{clean_body_html}</div>
            </body>
            </html>
            """
            return {"success": True, "html": full_html, "link": link, "title": title_text}
        except Exception as e:
            return {"success": False, "error": str(e), "html": f"<h3>로드 오류</h3><p>{e}</p>", "title": "오류"}

# ---------------------------------------------------------
# Streamlit UI & 세션 상태 복원
# ---------------------------------------------------------
@st.cache_resource
def get_backend():
    return DogDripBackend()

backend = get_backend()

# URL 쿼리 파라미터 파싱
query_params = st.query_params
url_article = query_params.get("article", None)

if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_article" not in st.session_state:
    st.session_state.selected_article = url_article
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""
if "current_articles" not in st.session_state:
    st.session_state.current_articles = []

# 새로고침 시 게시글 목록 자동 복구
if not st.session_state.current_articles:
    res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
    if res["success"]:
        st.session_state.current_articles = res["articles"]

# 최상단 이동용 앵커
st.markdown("<div id='app-top-anchor'></div>", unsafe_allow_html=True)
st.title("🐶 개드립 모바일 열람기")

# 상단 컨트롤 바
col_home, col_search, col_btn1, col_btn2 = st.columns([1.2, 3, 1, 1])

with col_home:
    if st.button("🏠 홈", use_container_width=True, type="secondary"):
        st.session_state.search_keyword = ""
        st.session_state.page = 1
        st.session_state.selected_article = None
        st.query_params.clear()
        st.rerun()

with col_search:
    keyword_input = st.text_input(
        "검색어", 
        value=st.session_state.search_keyword, 
        placeholder="검색어 입력", 
        label_visibility="collapsed"
    )

with col_btn1:
    if st.button("🔍 검색", use_container_width=True):
        st.session_state.search_keyword = keyword_input
        st.session_state.page = 1
        st.session_state.selected_article = None
        st.query_params.clear()
        st.rerun()

with col_btn2:
    if st.button("🔄 새로고침", use_container_width=True):
        st.rerun()

# ---------------------------------------------------------
# 본문 보기 화면
# ---------------------------------------------------------
if st.session_state.selected_article:
    st.query_params["article"] = st.session_state.selected_article

    current_links = [art["link"] for art in st.session_state.current_articles]
    current_idx = current_links.index(st.session_state.selected_article) if st.session_state.selected_article in current_links else -1

    can_prev = True if (st.session_state.page > 1 or current_idx > 0) else False
    can_next = True

    # 상단 컨트롤 버튼
    col_back, col_prev, col_next, col_link = st.columns([1.5, 1, 1, 1.5])
    
    with col_back:
        btn_back = st.button("⬅️ 목록으로", type="primary", use_container_width=True, key="main_btn_back")
        if btn_back:
            st.session_state.selected_article = None
            st.query_params.clear()
            st.rerun()
            
    with col_prev:
        btn_prev = st.button("◀ 이전글", disabled=not can_prev, use_container_width=True, key="main_btn_prev")
        if btn_prev:
            if current_idx > 0:
                st.session_state.selected_article = current_links[current_idx - 1]
            elif st.session_state.page > 1:
                st.session_state.page -= 1
                res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
                if res["success"] and res["articles"]:
                    st.session_state.current_articles = res["articles"]
                    st.session_state.selected_article = res["articles"][-1]["link"]
            st.query_params["article"] = st.session_state.selected_article
            st.rerun()

    with col_next:
        btn_next = st.button("다음글 ▶", disabled=not can_next, use_container_width=True, key="main_btn_next")
        if btn_next:
            if current_idx >= 0 and current_idx < len(current_links) - 1:
                st.session_state.selected_article = current_links[current_idx + 1]
            else:
                st.session_state.page += 1
                res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
                if res["success"] and res["articles"]:
                    st.session_state.current_articles = res["articles"]
                    st.session_state.selected_article = res["articles"][0]["link"]
            st.query_params["article"] = st.session_state.selected_article
            st.rerun()

    with col_link:
        st.markdown(
            f'''<a href="{st.session_state.selected_article}" target="_blank" style="text-decoration:none;">
                <button style="width:100%; height:38px; background-color:#ea580c; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">
                    🌐 원글 보기
                </button>
            </a>''', 
            unsafe_allow_html=True
        )

    # 📌 플로팅 버튼 및 스마트폰 뒤로가기 제어
    components.html("""
    <script>
        const doc = window.parent.document;
        const topWin = window.top;

        let oldBox = doc.getElementById('custom-floating-box');
        if (oldBox) oldBox.remove();

        const box = doc.createElement('div');
        box.id = 'custom-floating-box';
        box.style.cssText = `
            position: fixed;
            bottom: 80px;
            right: 16px;
            z-index: 999999;
            display: flex;
            flex-direction: column;
            gap: 8px;
            opacity: 0.45;
            transition: opacity 0.2s ease-in-out;
        `;

        box.onmouseenter = () => box.style.opacity = '1.0';
        box.onmouseleave = () => box.style.opacity = '0.45';
        box.ontouchstart = () => box.style.opacity = '1.0';
        box.ontouchend = () => setTimeout(() => box.style.opacity = '0.45', 1500);

        const btnStyle = `
            width:44px; height:44px;
            background:#1e40af; color:white;
            border:none; border-radius:50%;
            font-size:16px; font-weight:bold;
            cursor:pointer;
            box-shadow:0 3px 8px rgba(0,0,0,0.4);
            display:flex; align-items:center; justify-content:center;
            user-select:none; -webkit-tap-highlight-color:transparent;
        `;

        box.innerHTML = `
            <button id="float-top" style="${btnStyle}" title="게시글 상단으로">▲</button>
            <button id="float-prev" style="${btnStyle}" title="이전글">◀</button>
            <button id="float-next" style="${btnStyle}" title="다음글">▶</button>
        `;

        doc.body.appendChild(box);

        doc.getElementById('float-top').onclick = () => {
            const topEl = doc.getElementById('app-top-anchor');
            if (topEl) {
                topEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                topWin.scrollTo({ top: 0, behavior: 'smooth' });
            }
        };

        doc.getElementById('float-prev').onclick = () => {
            const btns = Array.from(doc.querySelectorAll('button'));
            const target = btns.find(b => b.innerText.includes('이전글'));
            if (target && !target.disabled) target.click();
        };

        doc.getElementById('float-next').onclick = () => {
            const btns = Array.from(doc.querySelectorAll('button'));
            const target = btns.find(b => b.innerText.includes('다음글'));
            if (target && !target.disabled) target.click();
        };

        // --- 📱 스마트폰 뒤로가기 스크립트 ---
        if (!topWin.history.state || topWin.history.state.mode !== 'detail') {
            topWin.history.pushState({ mode: 'detail' }, '', topWin.location.href);
        }

        topWin.onpopstate = function(e) {
            const btns = Array.from(doc.querySelectorAll('button'));
            const backBtn = btns.find(b => b.innerText.includes('목록으로'));
            if (backBtn) {
                backBtn.click();
            }
        };
    </script>
    """, height=0)

    st.divider()

    with st.spinner("본문 및 댓글 로딩 중..."):
        detail = backend.fetch_article_detail(st.session_state.selected_article)
        if detail["success"]:
            components.html(
                detail["html"], 
                height=2200, 
                scrolling=False
            )
        else:
            st.error(f"오류 발생: {detail['error']}")

# ---------------------------------------------------------
# 게시글 목록 화면
# ---------------------------------------------------------
else:
    st.query_params.clear()

    components.html("""
    <script>
        const doc = window.parent.document;
        const topWin = window.top;
        
        let oldBox = doc.getElementById('custom-floating-box');
        if (oldBox) oldBox.remove();
        
        topWin.onpopstate = null;
    </script>
    """, height=0)

    with st.spinner(f"페이지 {st.session_state.page} 데이터 수집 중..."):
        res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)

    if res["success"] and res["articles"]:
        st.session_state.current_articles = res["articles"]
        
        status_msg = f"🔍 '{st.session_state.search_keyword}' 검색결과 ({st.session_state.page} 페이지)" if st.session_state.search_keyword else f"📄 현재 {st.session_state.page} 페이지 (총 {len(res['articles'])}개 게시글)"
        st.caption(status_msg)
        
        for art in res["articles"]:
            if st.button(art["title"], key=art["link"], use_container_width=True):
                st.session_state.selected_article = art["link"]
                st.query_params["article"] = art["link"]
                st.rerun()

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
