#!/bin/sh

LOG_DIR=/home/whisper/stt-project/logs/api_app/
mkdir -p ${LOG_DIR}

nohup python /home/whisper/stt-project/src/api_app.py >> ${LOG_DIR}/api_app.log 2>&1 &

