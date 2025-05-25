# YouTube Script Crawler

YouTube 영상의 자막을 자동으로 다운로드하고 분석하여 Notion에 저장하는 웹 애플리케이션입니다.

## 주요 기능

- YouTube 영상 URL 입력으로 자막 자동 다운로드
- 한국어/영어 자막 지원 (우선순위: 한국어 → 한국어 자동생성 → 영어)
- GPT를 활용한 자막 분석 및 요약
- Notion 데이터베이스에 자동 저장
- 전체 스크립트 및 요약본 다운로드 기능

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/kimmans/younotion_nobase.git
cd younotion_nobase
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정
`.env` 파일을 생성하고 다음 변수들을 설정합니다:
```
OPENAI_API_KEY=your_openai_api_key
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
```

## 실행 방법

```bash
streamlit run app.py
```

## 사용 방법

1. 웹 브라우저에서 `http://localhost:8501` 접속
2. YouTube 영상 URL 입력
3. "분석 시작" 버튼 클릭
4. 분석이 완료되면 결과 확인 및 다운로드 가능

## 기술 스택

- Python
- Streamlit
- OpenAI GPT
- Notion API
- YouTube Transcript API
- PyTube

## 라이선스

jmhanmu@gmail.com 
