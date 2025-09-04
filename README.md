# Whisper

- Whisper + celery + redis를 사용하여 STT 병렬처리 제공
- 실시간 변환 API 제공
- GPU: NVIDIA A40 \* 3EA (GPU 1장당 6개의 프로세스)

### 준비

0. cuda 설치
1. redis 설치 및 기동
2. ./bin/faster_whisper_worker.sh 실행
3. ./bin/api_start.sh 실행

### API

1.  텍스트 파일 목록 조회
    - URL: /api/text_files
    - Method: GET
    - 설명: 날짜별 텍스트 파일 목록 트리를 JSON 형태로 반환
    - 응답예시
      ```
        {
            "20250904": ["샘플_1.txt"]
        }
      ```
2.  텍스트 파일 내용 조회

    - URL: /api/text_file_content
    - Method: GET
    - 설명: 지정된 텍스트 파일 내용을 읽어 반환합니다.
    - 쿼리 파라미터:
      | 파라미터명 | 필수 | 설명 |
      | ---- | ---- | ---- |
      | date | yes | yyMMdd 형식의 날짜 |
      | filename | yes | 조회할 텍스트 파일명(ex. 샘플\_1.txt) |
    - 요청예시

      ```
      GET /api/text_file_content?date=20250904&filename=샘플_1.txt
      ```

    - 응답예시
      ```
      {
        "content": "[1.36s -> 18.16s] 코로나19 예방수칙입니다. 손을 자주 씻기, 마스크 착용하기, 기침할 땐 입과 코 가리기, 발열, 기침, 인후통 등 증상 의심 시에는 1339 또는 보건소와 상담하시기 바랍니다."
      }
      ```

3.  비디오 파일 목록 조회

    - URL: /api/video_files
    - Method: GET
    - 설명: 날짜별 비디오 파일 목록을 반환합니다. (대상: '.mp4', '.webm', '.ogg', '.mkv', '.avi', '.mp3', '.wav')
    - 응답예시
      ```
      {
          "20250904": ["샘플_1.txt"]
      }
      ```

4.  비디오 파일 스트리밍

    - URL: /api/video_file_stream
    - Method: GET
    - 설명: 동영상 파일을 스트리밍 형식으로 반환합니다.
    - 쿼리 파라미터:
      | 파라미터명 | 필수 | 설명 |
      | ---- | ---- | ---- |
      | date | yes | yyMMdd 형식의 날짜 |
      | filename | yes | 스트리밍할 비디오 파일명(ex. 샘플\_1.wav) |
    - 요청예시

      ```
      GET /api/text_file_content?date=20250904&filename=샘플_1.wav
      ```

5.  비디오 파일 업로드 및 음성 인식 작업 생성

    - URL: /api/transcribe_video
    - Method: POST
    - Content-Type: multipart/form-data
    - 설명: 비디오 파일을 폴더에 저장하고 STT 작업 수행. 중복 파일명은 (1), (2) 등으로 자동 변경
    - 폼 데이터:
      | 파라미터명 | 필수 | 설명 |
      | ---- | ---- | ---- |
      | file | yes | 업로드할 비디오 파일 |
    - 응답예시

      ```
      //task_id는 "6.작업 상태 조회"에 사용됨.
      {
        "filename": "샘플_1.wav",
        "task_id": "c42baba2-4014-4d2e-99df-1aef34b9a0e5"
      }
      ```

6.  작업 상태 조회

    - URL: /api/task_status
    - Method: GET
    - 설명: Celery 비동기 작업 상태 및 결과를 조회합니다.
    - 쿼리 파라미터:
      | 파라미터명 | 필수 | 설명 |
      | ---- | ---- | ---- |
      | id | yes | 작업 상태를 확인할 ID(task_id) |
    - 요청예시

      ```
      GET /api/task_status?id=c42baba2-4014-4d2e-99df-1aef34b9a0e5
      ```

    - 응답예시
      ```
      {
        "date_done": "Thu, 04 Sep 2025 06:14:05 GMT",
        "result": {
            "output_file": "/home/whisper/stt-project/text/20250904/샘플_1.txt"
        },
        "status": "SUCCESS",
        "task_id": "c42baba2-4014-4d2e-99df-1aef34b9a0e5"
      }
      ```
