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
    # 인기순(sort=0) 정렬
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_pge&sort=0&ds=2000.01.01"
    # User-Agent 설정 (봇으로 인식되는 것을 방지)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} 
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 뉴스 아이템 추출 - 뉴스 검색 결과 리스트 항목 전체 (가장 포괄적인 선택자 중 하나)
        news_items = soup.select('ul.list_news > li.bx')
        
        top_3_news = []
        for i, item in enumerate(news_items):
            if len(top_3_news) >= 3: # 3개만 추출하고 중단
                break
                
            news_area = item.select_one('div.news_area')
            if not news_area:
                continue

            try:
                # --- [핵심 수정 부분] 네이버 최신 구조에 대응하여 제목과 링크 추출 ---
                
                # 1. 뉴스 제목의 링크를 담고 있는 <a> 태그를 선택
                # 일반적으로 뉴스 항목 내의 첫 번째 <a> 태그 또는 특정 구조를 가진 <a> 태그를 선택
                # 여기서는 'a.news_tit'이 작동하지 않을 경우를 대비하여 포괄적인 선택을 시도
                title_link_tag = news_area.select_one('a') # 뉴스 영역 내 첫 번째 <a> 태그
                
                link = None
                title = None

                if title_link_tag and 'href' in title_link_tag.attrs:
                    link = title_link_tag['href']
                    
                    # 2. <a> 태그 안에서 실제 제목 텍스트를 포함하는 span 태그 선택 (새로운 클래스)
                    # sds-comps-text 클래스를 사용하여 텍스트 추출 시도
                    title_tag = title_link_tag.select_one('span.sds-comps-text')
                    
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                    else:
                        # span 태그를 못 찾으면 <a> 태그 자체의 텍스트를 사용 (보험)
                        title = title_link_tag.get_text(strip=True)
                
                # 언론사 추출
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
                # 특정 뉴스 아이템 처리 중 오류 발생 시 건너뛰기
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
            assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다. (검색어 확인 또는 구조 변경 가능성)"
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