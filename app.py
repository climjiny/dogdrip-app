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

# 📌 모바일 환경에서 st.columns가 세로로 떨어지는 현상 방지 CSS
st.markdown("""
<style>
    /* 모바일 화면에서도 컬럼 레이아웃을 무조건 가로(Row) 6등분으로 강제 고정 */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }
    div[data-testid="stHorizontalBlock"] > div {
        flex: 1 1 0% !important;
        min-width: 0 !important;
    }
    /* 버튼 내부 패딩 조절하여 크기 최적화 */
    div[data-testid="stHorizontalBlock"] button {
        padding: 4px 0px !important;
        font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

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

    def fetch_article_detail(self, link, fallback_title=""):
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
            
            title_el = soup.select_one('h1.ed.title, div.document_title, h1.ed, h1, a.title')
            parsed_title = title_el.get_text(strip=True) if title_el else ""
            
            final_title = parsed_title if parsed_title else fallback_title
            if not final_title:
                final_title = "게시글 상세"

            content_el = soup.select_one('div.ed.article-content, div.xe_content, div.read_body, article')
            
            # 📌 2번 수정사항: 다양한 댓글 영역 셀렉터 추가 (댓글누락 완벽 방지)
            comment_el = soup.select_one('#commentbox, div.comment-list, #cmtPosition, div.comment, #comment, div.xe_comment')

            body_html = ""
            if content_el:
                body_html += f"<div class='article-content-box'>{str(content_el)}</div>"
            else:
                body_html += "<p style='color:gray; padding:20px;'>본문 내용을 찾을 수 없습니다.</p>"

            # 댓글 영역 처리
            if comment_el:
                cmt_count_el = comment_el.select_one('.comment-header, h3, .title, .comment-title')
                cmt_count_text = cmt_count_el.get_text(strip=True) if cmt_count_el else "댓글 목록"

                rebuilt_comments_html = f"<div class='comment-section-box'><h3 class='comment-section-header'>💬 {cmt_count_text}</h3>"

                # 댓글 항목 추출 패턴 보강
                cmt_items = comment_el.select('div[id^="comment_"], .comment-item, .comment-doc, .comment-content, li[id^="comment_"]')
                if not cmt_items:
                    cmt_items = comment_el.select('li, div.item')

                for cmt in cmt_items:
                    icon_el = cmt.select_one('img[src*="level"], img[src*="icon"], span.level, i.level')
                    icon_html = str(icon_el) if icon_el else ""

                    author_el = cmt.select_one('a[class*="member_"], span[class*="member_"], .author, .member_srl, .nick')
                    author_text = author_el.get_text(strip=True) if author_el else "익명"

                    date_el = cmt.select_one('.date, span.time, time, .time')
                    date_text = date_el.get_text(strip=True) if date_el else ""

                    content_body = cmt.select_one('.xe_content, .comment-body, .text, .content')
                    content_html = str(content_body) if content_body else ""

                    is_reply = False
                    if 'indent' in cmt.get('class', []) or 'reply' in cmt.get('class', []) or 'parent' in str(cmt.get('style', '')):
                        is_reply = True
                    margin_left = "16px" if is_reply else "0px"

                    if content_html:
                        rebuilt_comments_html += f"""
                        <div style="margin-left: {margin_left}; padding: 10px 12px; margin-bottom: 8px; background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 8px;">
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: nowrap; overflow: hidden;">
                                {f'<span style="display:inline-flex; align-items:center;">{icon_html}</span>' if icon_html else ''}
                                <span style="font-weight: 700; color: #2563eb; font-size: 14px; white-space: nowrap;">{author_text}</span>
                                <span style="color: #94a3b8; font-size: 12px; white-space: nowrap; margin-left: auto;">{date_text}</span>
                            </div>
                            <div style="color: #0f172a; font-size: 14px; line-height: 1.45;">
                                {content_html}
                            </div>
                        </div>
                        """

                rebuilt_comments_html += "</div>"
                body_html += rebuilt_comments_html

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

            # 📌 1번 수정사항: #article-title-target 앵커 추가 + 진입 즉시 제목 위치로 자동 스크롤
            full_html = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
                <meta name="referrer" content="no-referrer">
                <style>
                    html, body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        padding: 0;
                        margin: 0;
                        color: #1e293b;
                        line-height: 1.5;
                        background: #ffffff;
                        overflow-x: hidden;
                        touch-action: pan-x pan-y;
                        user-select: none;
                    }}

                    #zoom-container {{
                        transform-origin: 0 0;
                        width: 100%;
                        box-sizing: border-box;
                        padding: 10px;
                        transition: transform 0.05s linear;
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
                        margin-bottom: 12px;
                        padding-bottom: 10px;
                        border-bottom: 2px solid #e2e8f0;
                        word-break: keep-all;
                        line-height: 1.35;
                    }}
                    img, video {{
                        max-width: 100% !important;
                        height: auto !important;
                        display: block;
                        margin: 10px auto;
                        border-radius: 8px;
                    }}
                    .comment-section-box img {{
                        display: inline-block !important;
                        margin: 0 !important;
                        height: 16px !important;
                        width: auto !important;
                    }}
                    iframe {{
                        max-width: 100%;
                        width: 100%;
                        min-height: 250px;
                        border: none;
                    }}
                    .comment-section-box {{
                        margin-top: 16px;
                        padding-top: 10px;
                        border-top: 2px dashed #e2e8f0;
                    }}
                    .comment-section-header {{
                        font-size: 15px;
                        font-weight: 800;
                        color: #1e40af;
                        margin-bottom: 10px;
                    }}
                    a {{ color: #2563eb; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div id="zoom-container">
                    <div id="article-title-target"></div>
                    <div class="detail-header-label">게시글 상세</div>
                    <div class="article-title-box">📌 {final_title}</div>
                    <div class="article-body">{clean_body_html}</div>
                </div>

                <script>
                    // 📌 진입시 상단 제목 위치로 자동 스크롤
                    window.addEventListener('load', () => {{
                        setTimeout(() => {{
                            window.scrollTo({{ top: 0, behavior: 'smooth' }});
                            if (window.parent && window.parent.document) {{
                                const target = window.parent.document.getElementById('article-title-target');
                                if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                            }}
                        }}, 100);
                    }});

                    const container = document.getElementById('zoom-container');

                    let scale = 1;
                    let lastScale = 1;
                    let pointX = 0, pointY = 0;
                    let startX = 0, startY = 0;
                    let isDragging = false;
                    let initialDistance = 0;
                    let lastTapTime = 0;

                    function updateTransform() {{
                        scale = Math.min(Math.max(1, scale), 4);
                        if (scale === 1) {{
                            pointX = 0;
                            pointY = 0;
                        }}
                        container.style.transform = `translate(${{pointX}}px, ${{pointY}}px) scale(${{scale}})`;
                    }}

                    function toggleZoom() {{
                        if (scale > 1.05) {{
                            scale = 1;
                        }} else {{
                            scale = 1.5;
                        }}
                        pointX = 0;
                        pointY = 0;
                        updateTransform();
                    }}

                    document.addEventListener('dblclick', (e) => {{
                        e.preventDefault();
                        toggleZoom();
                    }});

                    document.addEventListener('wheel', (e) => {{
                        if (e.ctrlKey) {{
                            e.preventDefault();
                            const delta = e.deltaY < 0 ? 0.15 : -0.15;
                            scale += delta;
                            updateTransform();
                        }}
                    }}, {{ passive: false }});

                    document.addEventListener('touchend', (e) => {{
                        if (e.touches.length > 0) return;
                        
                        const now = new Date().getTime();
                        const timeDiff = now - lastTapTime;

                        if (timeDiff < 300 && timeDiff > 0) {{
                            toggleZoom();
                            e.preventDefault();
                        }}
                        lastTapTime = now;
                    }});

                    document.addEventListener('touchstart', (e) => {{
                        if (e.touches.length === 2) {{
                            initialDistance = Math.hypot(
                                e.touches[0].pageX - e.touches[1].pageX,
                                e.touches[0].pageY - e.touches[1].pageY
                            );
                        }} else if (e.touches.length === 1 && scale > 1) {{
                            isDragging = true;
                            startX = e.touches[0].clientX - pointX;
                            startY = e.touches[0].clientY - pointY;
                        }}
                    }});

                    document.addEventListener('touchmove', (e) => {{
                        if (e.touches.length === 2) {{
                            const currentDistance = Math.hypot(
                                e.touches[0].pageX - e.touches[1].pageX,
                                e.touches[0].pageY - e.touches[1].pageY
                            );
                            if (initialDistance > 0) {{
                                scale = lastScale * (currentDistance / initialDistance);
                                updateTransform();
                            }}
                        }} else if (e.touches.length === 1 && isDragging) {{
                            pointX = e.touches[0].clientX - startX;
                            pointY = e.touches[0].clientY - startY;
                            updateTransform();
                        }}
                    }}, {{ passive: false }});

                    document.addEventListener('touchend', (e) => {{
                        lastScale = scale;
                        isDragging = false;
                    }});
                </script>
            </body>
            </html>
            """
            return {"success": True, "html": full_html, "link": link, "title": final_title}
        except Exception as e:
            return {"success": False, "error": str(e), "html": f"<h3>로드 오류</h3><p>{e}</p>", "title": "오류"}

# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
backend = DogDripBackend()

query_params = st.query_params
url_article = query_params.get("article", None)

if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_article" not in st.session_state:
    st.session_state.selected_article = url_article
if "selected_title" not in st.session_state:
    st.session_state.selected_title = ""
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""
if "current_articles" not in st.session_state:
    st.session_state.current_articles = []

if not st.session_state.current_articles:
    res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
    if res["success"]:
        st.session_state.current_articles = res["articles"]

st.markdown("<div id='app-top-anchor'></div>", unsafe_allow_html=True)

# 헤더
st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px; margin-top: -10px;">
    <span style="font-size: 24px;">🐶</span>
    <span style="font-size: 20px; font-weight: 800; color: #0f172a; white-space: nowrap;">개드립 모바일 열람기</span>
</div>
""", unsafe_allow_html=True)

# 검색창
keyword_input = st.text_input(
    "검색어", 
    value=st.session_state.search_keyword, 
    placeholder="🔍 검색어 입력...", 
    label_visibility="collapsed"
)

current_links = [art["link"] for art in st.session_state.current_articles]
current_idx = current_links.index(st.session_state.selected_article) if (st.session_state.selected_article and st.session_state.selected_article in current_links) else -1
can_prev = True if (st.session_state.page > 1 or current_idx > 0) else False

# 6개 아이콘 버튼 1줄 배치
b_col1, b_col2, b_col3, b_col4, b_col5, b_col6 = st.columns(6)

with b_col1:
    if st.button("🏠", use_container_width=True, help="홈"):
        st.session_state.search_keyword = ""
        st.session_state.page = 1
        st.session_state.selected_article = None
        st.session_state.selected_title = ""
        st.query_params.clear()
        st.rerun()

with b_col2:
    if st.button("🔍", use_container_width=True, help="검색"):
        st.session_state.search_keyword = keyword_input
        st.session_state.page = 1
        st.session_state.selected_article = None
        st.session_state.selected_title = ""
        st.query_params.clear()
        st.rerun()

with b_col3:
    if st.button("🔄", use_container_width=True, help="새로고침"):
        st.rerun()

with b_col4:
    if st.button("📋", disabled=(not st.session_state.selected_article), use_container_width=True, help="목록"):
        st.session_state.selected_article = None
        st.session_state.selected_title = ""
        st.query_params.clear()
        st.rerun()

with b_col5:
    if st.button("◀", disabled=(not st.session_state.selected_article or not can_prev), use_container_width=True, help="이전글"):
        if current_idx > 0:
            st.session_state.selected_article = current_links[current_idx - 1]
            st.session_state.selected_title = st.session_state.current_articles[current_idx - 1]["title"]
        elif st.session_state.page > 1:
            st.session_state.page -= 1
            res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
            if res["success"] and res["articles"]:
                st.session_state.current_articles = res["articles"]
                st.session_state.selected_article = res["articles"][-1]["link"]
                st.session_state.selected_title = res["articles"][-1]["title"]
        st.query_params["article"] = st.session_state.selected_article
        st.rerun()

with b_col6:
    if st.button("▶", disabled=(not st.session_state.selected_article), use_container_width=True, help="다음글"):
        if current_idx >= 0 and current_idx < len(current_links) - 1:
            st.session_state.selected_article = current_links[current_idx + 1]
            st.session_state.selected_title = st.session_state.current_articles[current_idx + 1]["title"]
        else:
            st.session_state.page += 1
            res = backend.fetch_articles(page=st.session_state.page, keyword=st.session_state.search_keyword)
            if res["success"] and res["articles"]:
                st.session_state.current_articles = res["articles"]
                st.session_state.selected_article = res["articles"][0]["link"]
                st.session_state.selected_title = res["articles"][0]["title"]
        st.query_params["article"] = st.session_state.selected_article
        st.rerun()

# ---------------------------------------------------------
# 본문 보기 화면
# ---------------------------------------------------------
if st.session_state.selected_article:
    st.query_params["article"] = st.session_state.selected_article

    if current_idx >= 0 and not st.session_state.selected_title:
        st.session_state.selected_title = st.session_state.current_articles[current_idx]["title"]

    # 📌 진입시 제목 위치 앵커 삽입 및 스크롤 이벤트 발생
    st.markdown("<div id='article-title-target' style='scroll-margin-top: 10px;'></div>", unsafe_allow_html=True)

    components.html("""
    <script>
        const doc = window.parent.document;
        const topWin = window.top;

        // 게시물 진입 시 부모 창 스크롤을 제목 위치로 이동
        const titleTarget = doc.getElementById('article-title-target');
        if (titleTarget) {
            titleTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            topWin.scrollTo({ top: 0, behavior: 'smooth' });
        }

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
            width:42px; height:42px;
            background:#1e40af; color:white;
            border:none; border-radius:50%;
            font-size:15px; font-weight:bold;
            cursor:pointer;
            box-shadow:0 3px 8px rgba(0,0,0,0.3);
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
            const topEl = doc.getElementById('article-title-target');
            if (topEl) {
                topEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                topWin.scrollTo({ top: 0, behavior: 'smooth' });
            }
        };

        doc.getElementById('float-prev').onclick = () => {
            const btns = Array.from(doc.querySelectorAll('button'));
            const target = btns.find(b => b.innerText.trim() === '◀');
            if (target && !target.disabled) target.click();
        };

        doc.getElementById('float-next').onclick = () => {
            const btns = Array.from(doc.querySelectorAll('button'));
            const target = btns.find(b => b.innerText.trim() === '▶');
            if (target && !target.disabled) target.click();
        };

        if (!topWin.history.state || topWin.history.state.mode !== 'detail') {
            topWin.history.pushState({ mode: 'detail' }, '', topWin.location.href);
        }

        topWin.onpopstate = function(e) {
            const btns = Array.from(doc.querySelectorAll('button'));
            const backBtn = btns.find(b => b.innerText.trim() === '📋');
            if (backBtn) {
                backBtn.click();
            }
        };
    </script>
    """, height=0)

    st.divider()

    with st.spinner("본문 및 댓글 로딩 중..."):
        detail = backend.fetch_article_detail(
            st.session_state.selected_article, 
            fallback_title=st.session_state.get("selected_title", "")
        )
        if detail["success"]:
            components.html(
                detail["html"], 
                height=2500, 
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
                st.session_state.selected_title = art["title"]
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
