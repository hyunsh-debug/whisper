# tasks.py
import os
import time
from datetime import datetime
import torch
import whisper
from celery_app import app



@app.task(name="whisper_task.transcribe_video")
def transcribe_video(video_path: str):
    print(f"[변환 시작 => {video_path}]")
    TEXT_DIR = '/home/whisper/stt-project/text'

    start_time = time.time()

    basename = os.path.basename(video_path)
    filename_wo_ext = os.path.splitext(basename)[0]

    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = os.path.join(TEXT_DIR, date_str)
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{filename_wo_ext}.txt")

    model = whisper.load_model("large-v3-turbo")
    result = model.transcribe(video_path, language="ko")
    
    print(result["segments"])


    lines = [result["segments"].strip() for seg in result]
    text_with_newlines = lines

   # text = result["text"]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text_with_newlines)

    end_time = time.time()
    duration = round(end_time - start_time, 2)
    print(duration)
    return {
        "output_file": output_path
    }

if __name__ == "__main__":
    video_path = "/home/whisper/stt-project/video/test.webm"  # 테스트할 비디오 경로
    transcribe_video(video_path)

