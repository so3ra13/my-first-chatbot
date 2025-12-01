import streamlit as st
import os
import requests # 웹 페이지 요청을 위한 라이브러리
from bs4 import BeautifulSoup # HTML 파싱을 위한 라이브러리
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
    # 네이버 뉴스 검색 URL
    # 'sort=0'이 인기순(랭킹) 정렬 파라미터입니다.
    # 'ds=2000.01.01'은 검색 기간 제한을 없애기 위한 임의의 시작 날짜입니다.
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_pge&sort=0&ds=2000.01.01"
    headers = {'User-Agent': 'Mozilla/5.0'} # 봇으로 인식되는 것을 방지하기 위한 헤더 설정
    
    try:
        # 1. 웹 페이지 요청
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생

        # 2. HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 뉴스 아이템 추출
        # 네이버 검색 뉴스 리스트의 각 아이템을 나타내는 CSS 선택자
        news_items = soup.select('div.news_area')
        
        # 4. 상위 3개 뉴스 정보 추출
        top_3_news = []
        for i, item in enumerate(news_items[:3]): # 최대 3개까지만 처리
            try:
                # 제목 추출
                title_tag = item.select_one('a.news_tit')
                title = title_tag.get_text(strip=True) if title_tag else "제목 없음"
                
                # 링크 추출
                link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else "#"
                
                # 언론사 추출
                source_tag = item.select_one('a.info.press')
                source = source_tag.get_text(strip=True) if source_tag else "출처 불명"
                
                top_3_news.append({
                    "rank": i + 1,
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
if prompt := st.chat_input("검색할 키워드를 입력해 주세요 (예: 이강인, AI 반도체)"):
    # (1) 사용자 메시지 화면에 표시 & 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) 뉴스 검색 및 AI 응답 생성
    with st.chat_message("assistant"):
        # 사용자의 입력을 키워드로 간주하고 뉴스 검색 함수 호출
        keyword = prompt 
        news_results = get_naver_popular_news(keyword)
        
        # 응답 메시지 생성
        if isinstance(news_results, str):
            # 오류 메시지인 경우 그대로 출력
            assistant_reply = news_results
        elif not news_results:
            assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다."
        else:
            # 성공적으로 뉴스를 가져온 경우 마크다운 형식으로 출력
            reply_lines = [f"🌟 **'{keyword}'**에 대한 네이버 인기 뉴스 Top 3 입니다:"]
            for news in news_results:
                reply_lines.append(f"")
                # 제목을 링크로 표시 (클릭 가능)
                reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                reply_lines.append(f"   - *출처:* {news['source']}")
                
            assistant_reply = "\n".join(reply_lines)
            
        st.markdown(assistant_reply)
        
        # --- 선택적: Azure OpenAI 모델을 사용해 답변을 요약하거나 첨언하는 기능 ---
        # 이 기능을 활성화하려면 아래 주석을 해제하고 필요한 시스템 메시지를 추가하세요.
        # news_text = "\n".join([f"{n['title']} ({n['source']})" for n in news_results])
        # ai_prompt = f"다음 뉴스 목록을 보고 챗봇 사용자에게 친절하게 요약하거나 인사말을 덧붙여주세요:\n\n{news_text}"
        
        # response = client.chat.completions.create(
        #     model="gpt-4o-mini",
        #     messages=[
        #         {"role": "system", "content": "당신은 사용자에게 정보를 제공하는 친절한 챗봇입니다."},
        #         {"role": "user", "content": ai_prompt}
        #     ]
        # )
        # ai_comment = response.choices[0].message.content
        # st.markdown(f"\n---\n**AI 코멘트:** {ai_comment}")
        # assistant_reply += f"\n---\n**AI 코멘트:** {ai_comment}" 
        # -------------------------------------------------------------------

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})