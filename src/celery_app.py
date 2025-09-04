from celery import Celery

app = Celery(
    'whisper_stt',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
)


#import whisper_task  # 반드시 app 생성 이후 import 해야 함
import faster_whisper_task
