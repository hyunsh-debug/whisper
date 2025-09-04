from flask import Flask, jsonify, request, send_file, Response, abort
from flask_cors import CORS
import os
import re
from pydantic import BaseModel
from datetime import datetime
from werkzeug.utils import secure_filename
import time
from celery.result import AsyncResult
import requests
from urllib.parse import urlparse
from ipaddress import ip_address, ip_network


from faster_whisper_task import transcribe_video
from celery_app import app as celery_app

app = Flask(__name__)
CORS(app)

# 허용할 IP (단일 + CIDR 대역 혼합 가능)
ALLOWED_IPS = [
    "0.0.0.0/0"
]

# 베이스 경로 설정 (환경에 맞게 조정하세요)
TEXT_BASE_DIR = '/home/whisper/stt-project/text'
LOG_BASE_DIR = '/home/whisper/stt-project/logs/worker'
VIDEO_BASE_DIR = '/home/whisper/stt-project/video'

def get_text_file_tree():
    tree = {}
    for date_dir in sorted(os.listdir(TEXT_BASE_DIR)):
        date_path = os.path.join(TEXT_BASE_DIR, date_dir)
        if os.path.isdir(date_path):
            files = sorted(f for f in os.listdir(date_path) if f.endswith('.txt'))
            tree[date_dir] = files
    return tree

def is_ip_allowed(ip):
    try:
        ip_obj = ip_address(ip)
        for allowed in ALLOWED_IPS:
            if "/" in allowed:  # CIDR 대역
                if ip_obj in ip_network(allowed, strict=False):
                    return True
            else:  # 단일 IP
                if ip == allowed:
                    return True
        return False
    except ValueError:
        return False

@app.before_request
def limit_remote_addr():
    # X-Forwarded-For 헤더 우선 사용 (리버스 프록시 환경 고려)
    if "X-Forwarded-For" in request.headers:
        client_ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    else:
        client_ip = request.remote_addr

    if not is_ip_allowed(client_ip):
        return jsonify({"error": f"Access denied for IP {client_ip}"}), 403

def get_log_files():
    return sorted(
        f for f in os.listdir(LOG_BASE_DIR)
        if '.log' in f and os.path.isfile(os.path.join(LOG_BASE_DIR, f))
    )


def get_video_file_tree():
    tree = {}
    for date_dir in sorted(os.listdir(VIDEO_BASE_DIR)):
        date_path = os.path.join(VIDEO_BASE_DIR, date_dir)
        if os.path.isdir(date_path):
            files = sorted(f for f in os.listdir(date_path)
                           if f.lower().endswith(('.mp4', '.webm', '.ogg', '.mkv', '.avi', '.mp3', 'wav')))
            if files:
                tree[date_dir] = files
    return tree

def friendly_filename(filename):
    filename = filename.replace('/', '').replace('\\', '')
    filename = filename.replace(' ', '_')
    regex = '[^ㄱ-ㅎ가-힣a-zA-Z0-9._-]'
    filename = re.sub(regex, '', filename)
    return filename


@app.route('/api/text_files', methods=['GET'])
def api_text_files():
    """
    날짜별 텍스트 파일 목록 트리 반환
    {
        "20250730": ["file1.txt", "file2.txt"],
        "20250731": ["file1.txt", ...],
        ...
    }
    """
    tree = get_text_file_tree()
    return jsonify(tree)

@app.route('/api/text_file_content', methods=['GET'])
def api_text_file_content():
    """
    파일 경로 쿼리 파라미터로 받고, 텍스트 파일 내용 반환
    쿼리 예: /api/text_file_content?date=20250730&filename=초등_진수영_1학년12.txt
    """
    date = request.args.get('date')
    filename = request.args.get('filename')
    if not date or not filename:
        return jsonify({"error": "date and filename query parameters are required"}), 400
    file_path = os.path.join(TEXT_BASE_DIR, date, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "file not found"}), 404
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({"content": content})

@app.route('/api/log_files', methods=['GET'])
def api_log_files():
    """
    worker 로그 파일 목록 반환
    """
    logs = get_log_files()
    return jsonify(logs)

@app.route('/api/log_file_content', methods=['GET'])
def api_log_file_content():
    """
    로그 파일명 쿼리 파라미터로 받고 로그 내용 반환
    쿼리 예: /api/log_file_content?filename=worker0_20250730_160242.log
    """
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"error": "filename query parameter is required"}), 400
    file_path = os.path.join(LOG_BASE_DIR, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "log file not found"}), 404
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({"content": content})


@app.route('/api/video_files', methods=['GET'])
def api_video_files():
    videos = get_video_file_tree()
    return jsonify(videos)

@app.route('/api/video_file_stream', methods=['GET'])
def api_video_file_stream():
    """
    비디오 파일 스트리밍 (날짜별 디렉토리 구조 사용)
    쿼리 예: /api/video_file_stream?date=20250730&filename=sample.webm
    """
    date = request.args.get('date')
    filename = request.args.get('filename')
    
    if not date or not filename:
        return jsonify({"error": "date and filename query parameters are required"}), 400

    file_path = os.path.join(VIDEO_BASE_DIR, date, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "video file not found"}), 404

    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(file_path, mimetype='video/mp4', conditional=True)

    try:
        size = os.path.getsize(file_path)
        byte1, byte2 = 0, None

        m = range_header.replace('bytes=', '').split('-')
        if m[0]:
            byte1 = int(m[0])
        if len(m) == 2 and m[1]:
            byte2 = int(m[1])

        length = size - byte1
        if byte2 is not None:
            length = byte2 - byte1 + 1

        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data,
                      206,
                      mimetype='video/mp4',
                      content_type='video/mp4',
                      direct_passthrough=True)

        rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(length))
        return rv
    except Exception as e:
        print(f"Error streaming video: {e}")
        abort(500)

@app.route('/api/transcribe_video', methods=['POST'])
def api_transcribe_video():
    """
    비디오 파일 업로드 API
    - 폼 필드 이름: file
    - 저장 위치: /home/whisper/stt-project/video/yyyyMMdd/
    - 반환: filename, task_id
    """
    if 'file' not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "filename is empty"}), 400

    # 안전한 파일명으로 변환
#    filename = secure_filename(file.filename)
    filename = friendly_filename(file.filename)  # 여기로 변경

    # 오늘 날짜 폴더 생성 (yyyyMMdd)
    today_str = datetime.now().strftime('%Y%m%d')
    dated_dir = os.path.join(VIDEO_BASE_DIR, today_str)
    os.makedirs(dated_dir, exist_ok=True)  # 폴더 없으면 생성

    # 파일 중복 체크
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_name = filename

    while os.path.exists(os.path.join(dated_dir, unique_name)):
        unique_name = f"{name}({counter}){ext}"
        counter += 1

    save_path = os.path.join(dated_dir, unique_name)

    # 저장
    file.save(save_path)

    # Celery 비동기 작업 호출
    result = transcribe_video.delay(save_path)

    return jsonify({
        "filename": unique_name,
        "task_id": result.id
    }), 200


@app.route('/api/transcribe_video_from_cdn', methods=['POST'])
def api_transcribe_video_from_cdn():
    """
    CDN URL의 비디오 파일을 다운로드하여 STT 변환 API
    - JSON Body 예시: { "url": "https://cdn.example.com/path/to/video.mp4" }
    - 저장 위치: /home/whisper/stt-project/video/yyyyMMdd/
    - 반환: filename, task_id
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "url is required"}), 400

    file_url = data['url']
    parsed_url = urlparse(file_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return jsonify({"error": "Invalid URL"}), 400

    # CDN에서 파일 다운로드
    try:
        resp = requests.get(file_url, stream=True, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to download file from CDN: {str(e)}"}), 500

    # 원본 파일명 추출 후 안전한 파일명 변환
    original_filename = os.path.basename(parsed_url.path)
    filename = friendly_filename(original_filename)

    # 오늘 날짜 폴더 생성
    today_str = datetime.now().strftime('%Y%m%d')
    dated_dir = os.path.join(VIDEO_BASE_DIR, today_str)
    os.makedirs(dated_dir, exist_ok=True)

    # 중복 파일명 처리
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_name = filename
    while os.path.exists(os.path.join(dated_dir, unique_name)):
        unique_name = f"{name}({counter}){ext}"
        counter += 1

    save_path = os.path.join(dated_dir, unique_name)

    # CDN 파일 로컬 저장
    try:
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    # Celery 비동기 STT 변환 실행
    result = transcribe_video.delay(save_path)

    return jsonify({
        "filename": unique_name,
        "task_id": result.id
    }), 200


@app.route('/api/task_status', methods=['GET'])
def api_task_status():
    task_id = request.args.get('id')
    result = AsyncResult(task_id, app=celery_app)  # 🔧 여기가 핵심
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "result": result.result,
        "date_done": result.date_done
    }

    return jsonify(response)   


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)

