import os
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from urllib.parse import urlparse, parse_qs
import yt_dlp
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import streamlit as st
from zoneinfo import ZoneInfo

def analyze_with_gpt(transcript_text, title, channel, video_url, api_key):
    """
    GPT API를 사용해서 YouTube 자막 분석 및 인사이트 추출
    """
    try:
        # OpenAI 클라이언트 초기화 (문제 해결 버전)
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
너는 영상자막을 분석하는 AI 연구전문가야. Youtube 영상내용을 분석해서, 연구결과 및 인사이트를 도출해.

**영상 정보:**
- 제목: {title}
- 채널명: {channel}
- URL: {video_url}

**자막 내용:**
{transcript_text}

**분석지침:**
자막에서 다음 내용을 집중적으로 찾아 추출해:

- 구체적인 숫자, 통계, 퍼센티지 (출처 함께 기재)
- 연구 결과나 실험 데이터 (연구기관, 연구자 이름 포함)
- 기존 상식과 다른 새로운 관점이나 발견
- 놀랍거나 반직관적인 사실들

**요청사항:**
위 분석지침을 바탕으로 결과를 다음 형식으로 정확히 작성해:

## YouTube 영상 분석 리포트

**📺 영상 제목:** {title}
**🔗 URL:** {video_url}  
**👤 채널명:** {channel}
**📅 분석 일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### 🔍 주요 인사이트

(핵심 인사이트를 10개 항목으로 정리해. 
각 항목들은 숫자로 구분하고 ** 표시는 하지 않아.
각 인사이트는 구체적 숫자나 출처를 포함하여 작성하고, 기존 인식과 다른 점이 있다면 반드시 강조해.
)


"""
        
        # API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes YouTube video transcripts and extracts key insights."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result = response.choices[0].message.content
        if not result:
            raise Exception("GPT API가 빈 응답을 반환했습니다.")
        return result
        
    except Exception as e:
        print(f"❌ GPT API 분석 실패: {str(e)}")
        # 에러 세부 정보 출력
        if hasattr(e, 'response'):
            print(f"API 응답: {e.response}")
        return None

def save_analysis_report(analysis_text, title, video_id, output_dir="subtitles"):
    """분석 결과를 별도 파일로 저장"""
    try:
        clean_title = sanitize_filename(title)
        report_filename = f"{clean_title}_{video_id}_analysis.txt"
        report_filepath = os.path.join(output_dir, report_filename)
        
        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(analysis_text)
        
        return report_filepath
        
    except Exception as e:
        print(f"❌ 분석 리포트 저장 실패: {str(e)}")
        return None

def get_video_info(video_url):
    """YouTube 영상의 제목과 채널명 가져오기"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            title = info.get('title', 'Unknown_Title')
            uploader = info.get('uploader', 'Unknown_Channel')
            
            return title, uploader
            
    except Exception as e:
        print(f"⚠️ 영상 정보 가져오기 실패: {e}")
        return 'Unknown_Title', 'Unknown_Channel'

def sanitize_filename(text, max_length=50):
    """파일명으로 사용할 수 있도록 텍스트 정리"""
    # 특수문자 제거 및 공백을 언더스코어로 변경
    sanitized = re.sub(r'[^\w\s-]', '', text)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    
    # 길이 제한
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # 앞뒤 언더스코어 제거
    sanitized = sanitized.strip('_')
    
    return sanitized if sanitized else 'Unknown'

def extract_video_id(url):
    """YouTube URL에서 비디오 ID 추출"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # URL 파싱을 통한 추가 시도
    parsed_url = urlparse(url)
    if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query).get('v', [None])[0]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    
    return None

def save_to_notion(analysis_text, title, channel, video_url, database_id, notion_api_key):
    """
    분석 결과를 Notion 데이터베이스에 저장
    """
    try:
        if not analysis_text:
            raise Exception("분석 텍스트가 비어있습니다.")
            
        notion = Client(auth=notion_api_key)
        
        # 현재 날짜와 시간 (한국시간)
        korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
        current_time = korea_now.isoformat()
        
        # 주요 인사이트 추출 (### 🔍 주요 인사이트 다음 부분)
        insights = ""
        if "### 🔍 주요 인사이트" in analysis_text:
            insights = analysis_text.split("### 🔍 주요 인사이트")[1].strip()
        else:
            insights = analysis_text  # 전체 텍스트를 인사이트로 사용
        
        # 텍스트 길이 제한 (Notion API 제한 고려)
        if len(insights) > 2000:
            insights = insights[:2000] + "..."
        if len(analysis_text) > 2000:
            analysis_text = analysis_text[:2000] + "..."
        
        print(f"📝 Notion 저장 시도 중...")
        print(f"- 데이터베이스 ID: {database_id}")
        print(f"- 제목: {title}")
        print(f"- 채널명: {channel}")
        
        # Notion 데이터베이스에 새 페이지 생성
        new_page = {
            "parent": {"database_id": database_id},
            "properties": {
                "제목": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "채널명": {
                    "rich_text": [
                        {
                            "text": {
                                "content": channel
                            }
                        }
                    ]
                },
                "URL": {
                    "url": video_url
                },
                "분석일시": {
                    "date": {
                        "start": current_time
                    }
                },
                "주요 인사이트": {
                    "rich_text": [
                        {
                            "text": {
                                "content": insights
                            }
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": analysis_text
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        try:
            response = notion.pages.create(**new_page)
            if not response or "url" not in response:
                raise Exception("Notion API가 유효한 응답을 반환하지 않았습니다.")
            return response["url"]
        except Exception as api_error:
            print(f"❌ Notion API 호출 실패: {str(api_error)}")
            if hasattr(api_error, 'response'):
                print(f"API 응답 상세: {api_error.response}")
            raise
        
    except Exception as e:
        print(f"❌ Notion 저장 실패: {str(e)}")
        print(f"에러 타입: {type(e).__name__}")
        if hasattr(e, 'response'):
            print(f"API 응답: {e.response}")
        return None

def download_youtube_transcript(video_url, output_dir="subtitles", language='ko', openai_api_key=None, notion_api_key=None, notion_database_id=None):
    """
    YouTube 자막을 텍스트 파일로 다운로드 및 분석
    """
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            raise ValueError("유효하지 않은 YouTube URL입니다.")
        
        print(f"📹 비디오 ID: {video_id}")
        
        # 영상 정보 가져오기 (제목, 채널명)
        print("📋 영상 정보 가져오는 중...")
        title, uploader = get_video_info(video_url)
        print(f"📺 제목: {title}")
        print(f"👤 채널: {uploader}")
        
        # 사용 가능한 언어 목록 확인
        try:
            available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            print("📋 사용 가능한 자막 언어:")
            for transcript in available_transcripts:
                print(f"  - {transcript.language}: {transcript.language_code}")
        except Exception as e:
            print(f"⚠️ 자막 목록 조회 실패: {e}")
        
        # 자막 다운로드 시도 (언어 우선순위: 지정언어 → 한국어 → 영어)
        transcript = None
        used_language = language
        
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
            print(f"✅ {language} 자막 다운로드 성공")
        except:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
                used_language = 'ko'
                print("✅ 한국어 자막 다운로드 성공")
            except:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                    used_language = 'en'
                    print("✅ 영어 자막 다운로드 성공")
                except Exception as e:
                    raise Exception(f"사용 가능한 자막을 찾을 수 없습니다: {e}")
        
        if not transcript:
            raise Exception("자막 데이터를 가져올 수 없습니다.")
        
        # 텍스트 포맷터로 변환
        formatter = TextFormatter()
        text_formatted = formatter.format_transcript(transcript)
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # 파일명 생성 - {제목}_{채널명}_{video_id}_trans.txt
        clean_title = sanitize_filename(title)
        clean_uploader = sanitize_filename(uploader)
        filename = f"{clean_title}_{clean_uploader}_{video_id}_trans.txt"
        filepath = os.path.join(output_dir, filename)
        
        # 파일명이 너무 길면 조정
        if len(filename) > 200:  # Windows 파일명 길이 제한 고려
            clean_title = sanitize_filename(title, 30)
            clean_uploader = sanitize_filename(uploader, 20)
            filename = f"{clean_title}_{clean_uploader}_{video_id}_trans.txt"
            filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_formatted)
        
        print(f"🎉 자막 다운로드 완료!")
        print(f"📄 파일: {filename}")
        print(f"📊 텍스트 길이: {len(text_formatted):,} 글자")
        print(f"📝 자막 항목 수: {len(transcript):,} 개")
        
        # GPT API 분석 (API 키가 제공된 경우)
        analysis_filepath = None
        notion_url = None
        if openai_api_key:
            print(f"\n🤖 GPT API로 내용 분석 중...")
            analysis_result = analyze_with_gpt(text_formatted, title, uploader, video_url, openai_api_key)
            
            if analysis_result:
                # 로컬 파일로 저장
                analysis_filepath = save_analysis_report(analysis_result, title, video_id, output_dir)
                if analysis_filepath:
                    print(f"📊 분석 리포트 저장: {os.path.basename(analysis_filepath)}")
                
                # Notion에 저장 (API 키가 제공된 경우)
                if notion_api_key and notion_database_id:
                    print(f"\n📝 Notion에 저장 중...")
                    notion_url = save_to_notion(analysis_result, title, uploader, video_url, notion_database_id, notion_api_key)
                    if notion_url:
                        print(f"✅ Notion 저장 완료: {notion_url}")
        
        return filepath, analysis_filepath, notion_url
        
    except Exception as e:
        print(f"❌ 자막 다운로드 실패: {str(e)}")
        return None, None, None

def main():
    """메인 함수"""
    print("🎬 YouTube 자막 다운로더 + AI 분석 + Notion 저장")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # YouTube URL 입력받기
    video_url = input("YouTube URL을 입력하세요: ").strip()
    
    if not video_url:
        print("❌ URL이 입력되지 않았습니다.")
        return
    
    # Get API keys from environment variables
    openai_api_key = os.getenv('OPENAI_API_KEY')
    notion_api_key = os.getenv('NOTION_API_KEY')
    notion_database_id = os.getenv('NOTION_DATABASE_ID')
    
    if not openai_api_key:
        print("⚠️ OpenAI API 키가 .env 파일에 설정되지 않았습니다.")
        print("📝 자막만 다운로드합니다.")
    else:
        print("🤖 GPT AI 분석도 함께 진행합니다.")
    
    if not notion_api_key or not notion_database_id:
        print("⚠️ Notion API 키 또는 데이터베이스 ID가 설정되지 않았습니다.")
        print("📝 Notion 저장은 건너뜁니다.")
    
    # 기본 설정으로 다운로드 및 분석
    print("📥 자막 다운로드 중...")
    transcript_file, analysis_file, notion_url = download_youtube_transcript(
        video_url, 
        "subtitles", 
        "ko", 
        openai_api_key,
        notion_api_key,
        notion_database_id
    )
    
    if transcript_file:
        print(f"\n✅ 작업 완료!")
        print(f"📄 자막 파일: {os.path.basename(transcript_file)}")
        if analysis_file:
            print(f"📊 분석 파일: {os.path.basename(analysis_file)}")
        if notion_url:
            print(f"📝 Notion 페이지: {notion_url}")

def check_dependencies():
    """필요한 라이브러리 확인"""
    try:
        import youtube_transcript_api
        import yt_dlp
        print("✅ 기본 라이브러리가 설치되어 있습니다.")
        
        # OpenAI API 라이브러리 확인
        try:
            from openai import OpenAI
            print("✅ OpenAI API 라이브러리도 설치되어 있습니다.")
        except ImportError:
            print("⚠️ OpenAI API 라이브러리가 없습니다. 분석 기능을 사용하려면:")
            print("   pip install openai")
            print("   (자막 다운로드는 가능합니다)")
            
        return True
    except ImportError as e:
        print("❌ 필요한 라이브러리를 설치해주세요:")
        print("pip install youtube-transcript-api yt-dlp openai python-dotenv notion-client")
        print(f"누락된 모듈: {e}")
        return False

def search_youtube_videos(query, max_results=3, offset=0):
    """
    YouTube Data API를 사용하여 비디오 검색 (페이지네이션 지원)
    offset: 0, 10, 20 ...
    """
    try:
        youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        page_token = None
        results_to_skip = offset
        videos = []
        while results_to_skip >= 0:
            search_response = youtube.search().list(
                q=query,
                part='snippet',
                maxResults=max_results,
                type='video',
                pageToken=page_token
            ).execute()
            items = search_response.get('items', [])
            if results_to_skip < max_results:
                items = items[results_to_skip:]
                for item in items:
                    video_data = {
                        'title': item['snippet']['title'],
                        'channel': item['snippet']['channelTitle'],
                        'thumbnail': item['snippet']['thumbnails']['high']['url'],
                        'video_id': item['id']['videoId'],
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    }
                    videos.append(video_data)
                break
            else:
                results_to_skip -= max_results
                page_token = search_response.get('nextPageToken')
                if not page_token:
                    break
        return videos[:max_results]
    except HttpError as e:
        print(f"❌ YouTube API 오류: {str(e)}")
        return []
    except Exception as e:
        print(f"❌ 검색 중 오류 발생: {str(e)}")
        return []

if __name__ == "__main__":
    if check_dependencies():
        main()
    else:
        print("\n라이브러리 설치 후 다시 실행해주세요.")