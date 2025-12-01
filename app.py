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
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_keyword}&sm=tab_opt&sort=0&photo=0&field=0&pd=0&ds=&de=&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so:r,p:all,a:all"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    } 
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = soup.select('div.sds-comps-vertical-layout.sds-comps-full-layout')
        
        if not news_items:
            news_items = soup.select('div.sds-comps-base-layout') or \
                        soup.select('ul.list_news > li.bx')
        
        if not news_items:
            return []

        top_3_news = []
        
        for item in news_items:
            if len(top_3_news) >= 3:
                break
            
            try:
                link_tag = item.select_one('a[href*="naver.com"]')
                if not link_tag:
                    continue
                
                link = link_tag.get('href', '')
                if not link:
                    continue
                
                title_tag = item.select_one('span.sds-comps-text.sds-comps-text-ellipsis')
                if not title_tag:
                    title_tag = item.select_one('span.sds-comps-text')
                
                if title_tag:
                    title = title_tag.get_text(strip=True)
                else:
                    title = link_tag.get_text(strip=True)
                
                source_tag = item.select_one('a.info.press') or \
                           item.select_one('a.info') or \
                           item.select_one('div.sds-comps-profile span')
                
                source = source_tag.get_text(strip=True) if source_tag else "출처 불명"
                
                # 기사 본문 미리보기 추출 (요약용)
                summary_tag = item.select_one('div.news_dsc') or \
                             item.select_one('div.dsc_txt_wrap') or \
                             item.select_one('a.dsc_txt_wrap')
                
                summary = summary_tag.get_text(strip=True) if summary_tag else ""
                
                if title and link and len(title) > 5:
                    top_3_news.append({
                        "rank": len(top_3_news) + 1,
                        "title": title,
                        "link": link,
                        "source": source,
                        "summary": summary
                    })
                    
            except Exception as e:
                print(f"뉴스 아이템 처리 중 오류: {e}")
                continue

        return top_3_news

    except requests.exceptions.RequestException as e:
        return f"🚨 웹 요청 오류 발생: {e}"
    except Exception as e:
        return f"🚨 뉴스 데이터를 처리하는 중 오류 발생: {e}"


def get_article_content(url):
    """
    기사 URL에서 본문을 추출합니다.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 뉴스 본문 선택자
        article_body = soup.select_one('#dic_area') or \
                      soup.select_one('#articeBody') or \
                      soup.select_one('.article_body') or \
                      soup.select_one('#newsEndContents')
        
        if article_body:
            # 불필요한 태그 제거
            for tag in article_body.select('script, style, iframe'):
                tag.decompose()
            return article_body.get_text(strip=True)
        
        return None
        
    except Exception as e:
        print(f"기사 내용 추출 오류: {e}")
        return None


def summarize_article_with_ai(article_content, user_query=""):
    """
    Azure OpenAI를 사용하여 기사를 요약합니다.
    """
    try:
        if user_query:
            prompt = f"다음 기사를 읽고 사용자의 질문에 답해주세요.\n\n질문: {user_query}\n\n기사 내용:\n{article_content[:3000]}"
        else:
            prompt = f"다음 기사를 3-4문장으로 요약해주세요:\n\n{article_content[:3000]}"
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OAI_DEPLOYMENT", "gpt-4"),
            messages=[
                {"role": "system", "content": "당신은 뉴스 기사를 요약하고 분석하는 전문가입니다. 간결하고 명확하게 답변해주세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"AI 요약 중 오류 발생: {e}"


def find_related_articles(news_list, keyword):
    """
    뉴스 목록에서 특정 키워드와 관련된 기사를 찾습니다.
    """
    related = []
    keyword_lower = keyword.lower()
    
    for news in news_list:
        title_lower = news['title'].lower()
        summary_lower = news.get('summary', '').lower()
        
        if keyword_lower in title_lower or keyword_lower in summary_lower:
            related.append(news)
    
    return related


# Azure OpenAI 클라이언트 설정
try:
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OAI_KEY"),
        api_version="2024-05-01-preview",
        azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
    )
    ai_available = True
except Exception as e:
    st.warning("⚠️ Azure OpenAI 설정을 확인해주세요. AI 기능이 제한됩니다.")
    client = None
    ai_available = False

# 대화기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 최근 검색한 뉴스 저장
if "recent_news" not in st.session_state:
    st.session_state.recent_news = []

# 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 받기
if prompt := st.chat_input("검색할 키워드를 입력하거나 질문해주세요"):
    # 사용자 메시지 표시
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 응답 생성
    with st.chat_message("assistant"):
        prompt_lower = prompt.lower()
        
        # 1. 기사 요약 요청 감지
        if any(word in prompt_lower for word in ['요약', '요약해', '정리', '정리해']):
            if not st.session_state.recent_news:
                assistant_reply = "먼저 뉴스를 검색해주세요. 예: '삼성' 또는 'AI 반도체'"
            elif not ai_available:
                assistant_reply = "AI 요약 기능을 사용하려면 Azure OpenAI 설정이 필요합니다."
            else:
                with st.spinner("기사를 요약하는 중입니다..."):
                    summaries = []
                    for news in st.session_state.recent_news:
                        article_content = get_article_content(news['link'])
                        if article_content:
                            summary = summarize_article_with_ai(article_content)
                            summaries.append(f"**{news['rank']}. {news['title']}**\n{summary}\n")
                        else:
                            summaries.append(f"**{news['rank']}. {news['title']}**\n(본문을 가져올 수 없습니다)\n")
                    
                    assistant_reply = "📝 **기사 요약**\n\n" + "\n".join(summaries)
        
        # 2. 관련 기사 검색 요청 감지
        elif '관련' in prompt_lower and ('기사' in prompt_lower or '뉴스' in prompt_lower):
            if not st.session_state.recent_news:
                assistant_reply = "먼저 뉴스를 검색해주세요."
            else:
                # 키워드 추출 (간단한 방법)
                words = prompt.split()
                search_keyword = None
                for i, word in enumerate(words):
                    if '관련' in word and i > 0:
                        search_keyword = words[i-1].strip('이랑').strip()
                        break
                
                if search_keyword:
                    related = find_related_articles(st.session_state.recent_news, search_keyword)
                    if related:
                        reply_lines = [f"🔍 **'{search_keyword}'** 관련 기사:\n"]
                        for news in related:
                            reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                            reply_lines.append(f"   *출처: {news['source']}*\n")
                        assistant_reply = "\n".join(reply_lines)
                    else:
                        assistant_reply = f"'{search_keyword}'와 관련된 기사를 찾지 못했습니다."
                else:
                    assistant_reply = "어떤 키워드와 관련된 기사를 찾으시나요? 예: 'AI랑 관련된 기사가 있어?'"
        
        # 3. 일반 뉴스 검색
        else:
            with st.spinner("뉴스를 검색 중입니다..."):
                keyword = prompt.strip()
                news_results = get_naver_popular_news(keyword)
            
            if isinstance(news_results, str):
                assistant_reply = news_results
            elif not news_results:
                assistant_reply = f"👉 **'{keyword}'**에 대한 인기 뉴스를 찾을 수 없습니다.\n\n다른 키워드로 다시 시도해보세요."
            else:
                # 검색 결과 저장
                st.session_state.recent_news = news_results
                
                reply_lines = [f"🌟 **'{keyword}'**에 대한 네이버 인기 뉴스 Top {len(news_results)} 입니다:\n"]
                for news in news_results:
                    reply_lines.append(f"**{news['rank']}.** [{news['title']}]({news['link']})")
                    reply_lines.append(f"   *출처: {news['source']}*\n")
                
                if ai_available:
                    reply_lines.append("\n💡 **이렇게 물어보세요:**")
                    reply_lines.append("- '이 기사 요약해줘'")
                    reply_lines.append("- 'AI랑 관련된 기사가 있어?'")
                
                assistant_reply = "\n".join(reply_lines)
            
        st.markdown(assistant_reply)

    # AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})