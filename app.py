import streamlit as st
import os
import requests 
from bs4 import BeautifulSoup 
from openai import AzureOpenAI
from dotenv import load_dotenv
import urllib.parse

# 환경 변수 로드
load_dotenv()

st.title("📰 네이버 인기 뉴스 검색 챗봇")
st.markdown("키워드를 입력하시면 네이버 뉴스에서 관련 인기 뉴스 **3개**를 뽑아 드립니다.")

def get_naver_popular_news(keyword):
    """
    네이버 뉴스에서 키워드를 검색하여 인기순 뉴스 3개를 추출합니다.
    """
    # URL 인코딩 추가
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_keyword}&sm=tab_opt&sort=0&photo=0&field=0&pd=0&ds=&de=&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so:r,p:all,a:all"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    } 
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 스크린샷에서 확인된 구조: div.sds-comps-vertical-layout 내부의 항목들
        news_items = soup.select('div.sds-comps-vertical-layout.sds-comps-full-layout')
        
        if not news_items:
            # 대체 선택자
            news_items = soup.select('div.sds-comps-base-layout') or \
                        soup.select('ul.list_news > li.bx')
        
        if not news_items:
            return []

        top_3_news = []
        
        for item in news_items:
            if len(top_3_news) >= 3:
                break
            
            try:
                # 스크린샷 구조에 맞춘 선택자
                # 1. 링크 추출: a 태그에서 href 속성
                link_tag = item.select_one('a[href*="naver.com"]')
                if not link_tag:
                    continue
                
                link = link_tag.get('href', '')
                if not link:
                    continue
                
                # 2. 제목 추출: span.sds-comps-text 내부의 텍스트
                title_tag = item.select_one('span.sds-comps-text.sds-comps-text-ellipsis')
                if not title_tag:
                    title_tag = item.select_one('span.sds-comps-text')
                
                if title_tag:
                    title = title_tag.get_text(strip=True)
                else:
                    # a 태그의 텍스트 사용
                    title = link_tag.get_text(strip=True)
                
                # 3. 언론사 추출
                source_tag = item.select_one('a.info.press') or \
                           item.select_one('a.info') or \
                           item.select_one('div.sds-comps-profile span')
                
                source = source_tag.get_text(strip=True) if source_tag else "출처 불명"
                
                if title and link and len(title) > 5:  # 제목이 너무 짧으면 제외
                    top_3_news.append({
                        "rank": len(top_3_news) + 1,
                        "title": title,
                        "link": link,
                        "source": source
                    })
                    
            except Exception as e:
                print(f"뉴스 아이템 처리 중 오류: {e}")
                continue

        return top_3_news

    except requests.exceptions.RequestException as e:
        return f"🚨 웹 요청 오류 발생: {e}"
    except Exception as e:
        return f"🚨 뉴스 데이터를 처리하는 중 오류 발생: {e}"


# Azure OpenAI 클라이언트 설정 (선택사항)
try:
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OAI_KEY"),
        api_version="2024-05-01-preview",
        azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
    )
except Exception as e:
    st.warning("Azure OpenAI 설정을 확인해주세요.")
    client = None

# 대화기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 받기
if prompt := st.chat_input("검색할 키워드를 입력해 주세요 (예: 삼성, AI 반도체)"):
    # 사용자 메시지 표시
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 뉴스 검색 및 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("뉴스를 검색 중입니다..."):
            keyword = prompt.strip()
            news_results = get_naver_popular_news(keyword)
        
        # 응답 메시지 생성
        if isinstance(news_results, str):
            assistant_reply = news_results
        elif not news_results:
            assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다.\n\n다른 키워드로 다시 시도해보세요."
        else:
            reply_lines = [f"🌟 **'{keyword}'**에 대한 네이버 인기 뉴스 Top {len(news_results)} 입니다:\n"]
            for news in news_results:
                reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                reply_lines.append(f"   *출처: {news['source']}*\n")
                
            assistant_reply = "\n".join(reply_lines)
            
        st.markdown(assistant_reply)

    # AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})