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

# --- 뉴스 검색 기능 최종 수정 ---
def get_naver_popular_news(keyword):
    """
    네이버 뉴스에서 키워드를 검색하여 인기순(랭킹) 뉴스 3개를 추출합니다.
    """
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_pge&sort=0&ds=2000.01.01"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} 
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 뉴스 아이템 추출: 가장 보편적인 리스트 항목 선택자
        news_items = soup.select('ul.list_news > li.bx')
        
        # 이 선택자로 아이템을 못 찾을 경우, 뉴스 영역 전체를 나타내는 다른 선택자 시도
        if not news_items:
             # 더 포괄적인 선택자 (예: 'div.news_area'를 포함하는 상위 컴포넌트)
             # 그러나 li.bx가 가장 안정적이므로, 이 부분은 그대로 두고 내부 로직에 집중
             pass

        top_3_news = []
        for i, item in enumerate(news_items):
            if len(top_3_news) >= 3:
                break
                
            news_area = item.select_one('div.news_area')
            if not news_area:
                continue

            try:
                # --- [최종 수정: 제목, 링크, 언론사 추출] ---
                
                # 1. 제목 링크 태그 (<a>) 찾기: 두 가지 일반적인 경우를 모두 시도
                title_link_tag = news_area.select_one('a.news_tit') or news_area.select_one('a')
                
                link = None
                title = None

                if title_link_tag and 'href' in title_link_tag.attrs:
                    link = title_link_tag['href']
                    
                    # 2. 제목 텍스트 추출: 최신 구조(span.sds-comps-text) 또는 이전 구조(<a> 텍스트) 시도
                    title_text_tag = title_link_tag.select_one('span.sds-comps-text')
                    
                    if title_text_tag:
                        title = title_text_tag.get_text(strip=True)
                    else:
                        # span 태그를 못 찾으면 <a> 태그 자체의 텍스트를 사용
                        title = title_link_tag.get_text(strip=True)
                
                # 3. 언론사 추출: 여러 가능한 선택자를 순차적으로 시도
                source_tag = news_area.select_one('a.info.press') or \
                             news_area.select_one('a.info') or \
                             news_area.select_one('span.info')
                
                source = source_tag.get_text(strip=True) if source_tag else "출처 불명"
                
                # 최종 검증 및 추가
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
if prompt := st.chat_input("검색할 키워드를 입력해 주세요 (예: 삼성, AI 반도체)"):
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
            assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다. (네이버 구조 변경 또는 검색어 확인 필요)"
        else:
            reply_lines = [f"🌟 **'{keyword}'**에 대한 네이버 인기 뉴스 Top 3 입니다:"]
            for news in news_results:
                reply_lines.append(f"")
                # 제목을 링크로 표시 (클릭 가능)
                reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                reply_lines.append(f"   - *출처:* {news['source']}")
                
            assistant_reply = "\n".join(reply_lines)
            
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})