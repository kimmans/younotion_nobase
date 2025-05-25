import streamlit as st
import os
from dotenv import load_dotenv
from main import download_youtube_transcript, get_video_info, analyze_with_gpt, save_to_notion
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_teddynote import logging

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
if 'input_key' not in st.session_state:
    st.session_state.input_key = 0

# 메인 타이틀
st.title("🎬 YouTube 보는 시간도 아깝다")
st.markdown("관심 있는 유튜브 URL만 입력하면, 알아서 요약하고 노션에 정리까지")

# URL 입력
video_url = st.text_input(
    "YouTube URL을 입력하세요",
    placeholder="https://www.youtube.com/watch?v=...",
    key=f"url_input_{st.session_state.input_key}"
)

# 버튼을 나란히 배치
col1, col2 = st.columns(2)
with col1:
    analyze_button = st.button("분석 시작", type="primary", use_container_width=True)
with col2:
    reset_button = st.button("초기화", use_container_width=True)

# 초기화 버튼 처리
if reset_button:
    st.session_state.results = None
    st.session_state.video_url = ""
    st.session_state.input_key += 1
    st.experimental_rerun()

# 분석 시작 버튼 처리
if analyze_button:
    if not video_url:
        st.error("YouTube URL을 입력해주세요.")
    else:
        st.session_state.video_url = video_url
        try:
            # 자막 다운로드 및 분석
            video_id = YouTube(video_url).video_id
            transcript = None
            used_language = None

            # 자막 다운로드 시도 (언어 우선순위: 한국어 → 한국어 자동생성 → 영어)
            try:
                # 먼저 사용 가능한 자막 목록 확인
                available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                st.info("📋 사용 가능한 자막 언어:")
                for transcript_item in available_transcripts:
                    st.write(f"  - {transcript_item.language}: {transcript_item.language_code}")
                
                # 자막 시도 순서: 한국어 수동 → 한국어 자동 → 영어 수동 → 영어 자동
                languages_to_try = [
                    ('ko', '한국어'),
                    ('en', '영어')
                ]
                
                for lang_code, lang_name in languages_to_try:
                    if transcript:
                        break
                        
                    try:
                        # 수동 생성 자막 시도
                        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_code])
                        used_language = lang_code
                        st.success(f"✅ {lang_name} 수동 생성 스크립트 생성 성공")
                    except:
                        try:
                            # 자동 생성 자막 시도
                            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                            # 자동 생성 자막 명시적으로 찾기
                            auto_generated = transcript_list.find_generated_transcript([lang_code])
                            if auto_generated:
                                transcript = auto_generated.fetch()
                                used_language = lang_code
                                st.success(f"✅ {lang_name} 자동 생성 스크립트 생성 성공")
                        except:
                            continue
                
                if not transcript:
                    st.warning("⚠️ 한국어 또는 영어 자막을 찾을 수 없습니다.")
                    st.info("현재 지원 언어: 한국어, 영어")
                    transcript = None
                    used_language = None
                    
            except Exception as e:
                st.warning("⚠️ 자막 목록을 가져올 수 없습니다.")
                st.info("동영상이 비공개이거나 자막이 비활성화되어 있을 수 있습니다.")
                transcript = None
                used_language = None
            
            if transcript:
                # Get video info
                title, channel = get_video_info(video_url)
                
                # Convert transcript to text
                transcript_text = "\n".join([f"{item['text']}" for item in transcript])
                
                # Generate summary using GPT
                api_keys = get_api_keys()
                if api_keys['openai']:
                    with st.spinner('🤖 AI가 영상을 분석하고 있습니다...'):
                        analysis_text = analyze_with_gpt(transcript_text, title, channel, video_url, api_keys['openai'])
                        
                        if analysis_text:
                            # Save analysis to Notion if API key is provided
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
                
                # 결과를 세션 상태에 저장
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
            if hasattr(e, 'response'):
                st.error(f"API 응답: {e.response}")

# 결과 표시 (세션 상태에서 가져옴)
if st.session_state.results:
    results = st.session_state.results
    st.success("✅ 분석이 완료되었습니다!")
    
    # 결과 컨테이너 생성
    results_container = st.container()
    
    with results_container:
        # 다운로드 버튼과 Notion 링크를 나란히 배치
        col1, col2 = st.columns(2)
        
        with col1:
            # 전체 스크립트 파일 다운로드
            if results['transcript_text']:
                st.download_button(
                    "📥 전체 스크립트 다운로드",
                    results['transcript_text'],
                    file_name=f"full_transcript_{results['language']}.txt",
                    mime="text/plain",
                    key="full_transcript_download"
                )
            
            # 요약 스크립트 파일 다운로드
            if results['analysis_text']:
                st.download_button(
                    "📊 요약 스크립트 다운로드",
                    results['analysis_text'],
                    file_name=f"summary_{results['language']}.txt",
                    mime="text/plain",
                    key="summary_download"
                )
        
        with col2:
            # Notion 링크
            if results['notion_url']:
                st.markdown("### 📝 Notion")
                st.markdown(f"[Notion에서 보기]({results['notion_url']})")
    

# 푸터
st.markdown("---")
st.markdown("Made by jmhanmu@gmail.com❤️ ")
