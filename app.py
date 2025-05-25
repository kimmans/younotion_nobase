import streamlit as st
import os
from dotenv import load_dotenv
from main import download_youtube_transcript, get_video_info, analyze_with_gpt, save_to_notion, search_youtube_videos
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_teddynote import logging
import re

# 프록시 설정 (스트림릿 클라우드 환경에서만 사용)
if 'STREAMLIT_SERVER' in os.environ:
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY')
    }
    YouTubeTranscriptApi._proxies = proxies

# User-Agent 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# YouTubeTranscriptApi에 headers 전달
YouTubeTranscriptApi._headers = headers

# 타임아웃 설정
YouTubeTranscriptApi._timeout = 30  # 30초로 설정

# 페이지 설정
st.set_page_config(
    page_title="YouTube 분석기",
    page_icon="🎬",
    layout="wide"
)

# 환경 변수 로드
load_dotenv()

# 프로젝트 이름
logging.langsmith("jmango-yp")

# API 키 가져오기
def get_api_keys():
    return {
        'openai': os.getenv('OPENAI_API_KEY'),
        'notion': os.getenv('NOTION_API_KEY'),
        'notion_db': os.getenv('NOTION_DATABASE_ID')
    }

# 세션 상태 초기화
if 'results' not in st.session_state:
    st.session_state.results = None
if 'video_url' not in st.session_state:
    st.session_state.video_url = ""
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'search_offset' not in st.session_state:
    st.session_state.search_offset = 0

# run_search 함수 정의 (검색 실행 로직)
def run_search():
    if st.session_state.search_input.strip():
        with st.spinner("🔍 검색 중..."):
            videos = search_youtube_videos(
                st.session_state.search_input,
                max_results=10,
                offset=st.session_state.search_offset
            )
            st.session_state.search_results = videos
            st.session_state.search_query = st.session_state.search_input

# --- 초기화 함수 정의 ---
def reset_search():
    st.session_state.search_results = []
    st.session_state.search_query = ""
    st.session_state.video_url = ""
    st.session_state.results = None
    st.session_state.search_offset = 0
    st.rerun()

# --- 메인 화면 ---
st.title("🎬 YouTube 보는 시간도 아깝다")
st.markdown("관심 있는 유튜브 영상을 검색하고, 알아서 요약하고 노션에 정리까지")

# --- 사이드바에 검색 입력 및 버튼 ---
with st.sidebar:
    st.markdown("### 🔍 YouTube 검색")
    search_value = st.session_state.get("search_input", "")
    st.text_input(
        "검색어를 입력하세요",
        placeholder="검색어를 입력하세요...",
        key="search_input",
        value=search_value,
        on_change=run_search
    )
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("검색", key="search_button"):
            run_search()
    with btn_col2:
        if st.button("초기화", key="reset_button"):
            reset_search()

    st.markdown("---")
    st.markdown("#### 또는 직접 유튜브 URL 입력")
    url_input = st.text_input(
        "유튜브 URL을 입력하세요",
        placeholder="https://www.youtube.com/watch?v=...",
        key="direct_url_input"
    )
    if st.button("이 URL 분석", key="analyze_direct_url"):
        if url_input.strip():
            st.session_state.video_url = url_input.strip()
            st.session_state.results = None
            st.rerun()
        else:
            st.warning("유튜브 URL을 입력해주세요.")

# 항상 세션 상태의 검색 결과를 보여줌
if st.session_state.search_results:
    st.markdown(f"### 📺 '{st.session_state.search_query}' 검색 결과")
    cols = st.columns(5)  # 5열 카드형, 10개면 2줄로 나옴
    for idx, video in enumerate(st.session_state.search_results):
        with cols[idx % 5]:
            st.markdown(
                f"""
                <div style="border:1px solid #eee; border-radius:10px; padding:8px; margin-bottom:10px; background-color:#fcfcfc; text-align:center;">
                    <img src="{video['thumbnail']}" width="100%" style="border-radius:6px; margin-bottom:4px; max-height:90px; object-fit:cover;">
                    <div style="font-weight:bold; font-size:0.95em; margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{video['title']}</div>
                    <div style="color:#666; font-size:0.85em; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">👤 {video['channel']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("이 영상 분석하기", key=f"select_{video['video_id']}"):
                st.session_state.video_url = video['url']
                st.session_state.results = None
                st.rerun()
    # 페이지네이션 버튼 (이전/다음)
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)  # 카드와 버튼 사이 여백

    pag_col1, pag_col2, pag_col3 = st.columns([2, 1, 2])
    with pag_col1:
        if st.session_state.search_offset >= 10:
            if st.button("이전 10개", key="prev_10"):
                st.session_state.search_offset -= 10
                run_search()
    with pag_col2:
        pass  # 가운데 비움(버튼이 중앙에 오도록)
    with pag_col3:
        if st.button("다음 10개", key="next_10"):
            st.session_state.search_offset += 10
            run_search()

# 분석 시작 처리 부분 시작 전에 디버깅 정보 추가
# st.write("---")
# st.write("디버깅 정보:")
# st.write(f"세션 상태의 video_url: {st.session_state.video_url}")
# st.write(f"분석 시작 조건: {bool(st.session_state.video_url)}")

# 분석 시작 처리
if st.session_state.video_url:
    video_url = st.session_state.video_url
    try:
        # 자막 다운로드 및 분석
        video_id = YouTube(video_url).video_id
        transcript = None
        used_language = None

        try:
            # 자동 생성 자막만 시도 (한국어 → 영어 순서)
            transcript = None
            used_language = None
            try:
                st.info("🔍 한국어 자동 생성 자막을 찾는 중...")
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                auto_generated = transcript_list.find_generated_transcript(['ko'])
                if auto_generated:
                    transcript = auto_generated.fetch()
                    used_language = 'ko'
                    st.success("✅ 한국어 자동 생성 스크립트 생성 성공")
                else:
                    st.warning("⚠️ 한국어 자동 생성 자막을 찾을 수 없습니다.")
            except Exception as e:
                st.warning(f"⚠️ 한국어 자동 생성 자막 시도 실패: {str(e)}")
                # 영어 자동 생성 자막만 시도
                try:
                    st.info("🔍 영어 자동 생성 자막을 찾는 중...")
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    auto_generated = transcript_list.find_generated_transcript(['en'])
                    if auto_generated:
                        transcript = auto_generated.fetch()
                        used_language = 'en'
                        st.success("✅ 영어 자동 생성 스크립트 생성 성공")
                    else:
                        st.warning("⚠️ 영어 자동 생성 자막을 찾을 수 없습니다.")
                except Exception as e:
                    st.warning(f"⚠️ 영어 자동 생성 자막 시도 실패: {str(e)}")
                    transcript = None
                    used_language = None

            if transcript:
                # Get video info
                title, channel = get_video_info(video_url)
                transcript_text = "\n".join([f"{item['text']}" for item in transcript])
                api_keys = get_api_keys()
                if api_keys['openai']:
                    with st.spinner('🤖 AI가 영상을 분석하고 있습니다...'):
                        analysis_text = analyze_with_gpt(transcript_text, title, channel, video_url, api_keys['openai'])
                        if analysis_text:
                            if api_keys['notion'] and api_keys['notion_db']:
                                with st.spinner('📝 Notion에 저장 중...'):
                                    notion_url = save_to_notion(
                                        analysis_text, 
                                        title, 
                                        channel, 
                                        video_url, 
                                        api_keys['notion_db'], 
                                        api_keys['notion']
                                    )
                                    if notion_url:
                                        st.success("✅ Notion에 저장되었습니다. 결과에서 링크를 확인하세요.")
                                    else:
                                        st.error("❌ Notion 저장에 실패했습니다.")
                        else:
                            st.error("❌ AI 분석에 실패했습니다.")
                st.session_state.results = {
                    'transcript': transcript,
                    'transcript_text': transcript_text,
                    'analysis_text': analysis_text if 'analysis_text' in locals() else None,
                    'notion_url': notion_url if 'notion_url' in locals() else None,
                    'language': used_language,
                    'title': title,
                    'channel': channel
                }
        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {str(e)}")
            transcript = None
            used_language = None
    except Exception as e:
        st.error(f"❌ 오류가 발생했습니다: {str(e)}")
        if hasattr(e, 'response'):
            st.error(f"API 응답: {e.response}")

# 결과 표시 (세션 상태에서 가져옴)
if st.session_state.results:
    results = st.session_state.results
    st.success("✅ 분석이 완료되었습니다!")
    results_container = st.container()
    
    with results_container:
        col1, col2 = st.columns(2)
        with col1:
            if results['transcript_text']:
                st.download_button(
                    "📥 전체 스크립트 다운로드",
                    results['transcript_text'],
                    file_name=f"full_transcript_{results['language']}.txt",
                    mime="text/plain",
                    key="full_transcript_download"
                )
            if results['analysis_text']:
                st.download_button(
                    "📊 요약 스크립트 다운로드",
                    results['analysis_text'],
                    file_name=f"summary_{results['language']}.txt",
                    mime="text/plain",
                    key="summary_download"
                )
        with col2:
            if results['notion_url']:
                st.markdown("### 📝 Notion")
                st.markdown(f"[Notion에서 보기]({results['notion_url']})")

# 푸터
st.markdown("---")
st.markdown("Made by jmhanmu@gmail.com❤️ ")
