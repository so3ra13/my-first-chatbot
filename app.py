import streamlit as st
import os
import requests 
from bs4 import BeautifulSoup 
from openai import AzureOpenAI
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일이 같은 폴더에 있어야 함)
load_dotenv()

st.title("📰 네이버 인기 뉴스 검색 챗봇")
st.markdown("키워드를 입력하시면 네이버 뉴스에서 관련 인기 뉴스 **3개**를 뽑아 드립니다.")

# --- 뉴스 검색 기능 추가 ---
def get_naver_popular_news(keyword):
    """
    네이버 뉴스에서 키워드를 검색하여 인기순(랭킹) 뉴스 3개를 추출합니다.
    """
    # URL 인코딩은 requests가 처리하므로, 여기서는 f-string만 사용
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_pge&sort=0&ds=2000.01.01"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} 
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 뉴스 아이템 추출 - 더 안정적인 선택자로 변경 ('ul.list_news'의 'li.bx' 항목)
        news_items = soup.select('ul.list_news > li.bx')
        
        top_3_news = []
        for i, item in enumerate(news_items):
            if len(top_3_news) >= 3: # 3개만 추출하고 중단
                break
                
            # 'div.news_area'는 각 리스트 항목(li.bx) 안에 있습니다.
            news_area = item.select_one('div.news_area')
            if not news_area:
                continue

            try:
                # 제목 추출
                title_tag = news_area.select_one('a.news_tit')
                title = title_tag.get_text(strip=True) if title_tag else None
                
                # 링크 추출
                link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else None
                
                # 언론사 추출
                # 언론사 정보는 'a.info.press' 또는 'a.info'의 텍스트로 찾을 수 있습니다.
                source_tag = news_area.select_one('a.info.press') or news_area.select_one('a.info')
                source = source_tag.get_text(strip=True) if source_tag else "출처 불명"
                
                # 제목과 링크가 유효한 경우에만 추가
                if title and link:
                    top_3_news.append({
                        "rank": len(top_3_news) + 1,
                        "title": title,
                        "link": link,
                        "source": source
                    })
            except Exception as e:
                print(f"뉴스 아이템 처리 중 오류 발생: {e}")
                continue

        return top_3_news

    except requests.exceptions.RequestException as e:
        return f"🚨 웹 요청 오류 발생: {e}"
    except Exception as e:
        return f"🚨 뉴스 데이터를 처리하는 중 오류 발생: {e}"
# -----------------------------


# 2. Azure OpenAI 클라이언트 설정 (AI 모델은 예비 기능으로 남겨둡니다)
# (실제 값은 .env 파일이나 여기에 직접 입력하세요)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OAI_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
)

# 3. 대화기록(Session State) 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("검색할 키워드를 입력해 주세요 (예: 이강인, AI 반도체)"):
    # (1) 사용자 메시지 화면에 표시 & 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) 뉴스 검색 및 AI 응답 생성
    with st.chat_message("assistant"):
        keyword = prompt 
        news_results = get_naver_popular_news(keyword)
        
        # 응답 메시지 생성
        if isinstance(news_results, str):
            assistant_reply = news_results
        elif not news_results:
            assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다. (검색어 확인 또는 구조 변경 가능성)"
        else:
            reply_lines = [f"🌟 **'{keyword}'**에 대한 네이버 인기 뉴스 Top 3 입니다:"]
            for news in news_results:
                reply_lines.append(f"")
                reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                reply_lines.append(f"   - *출처:* {news['source']}")
                
            assistant_reply = "\n".join(reply_lines)
            
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})