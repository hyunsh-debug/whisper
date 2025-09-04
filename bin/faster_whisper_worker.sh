#!/bin/bash

export PYTHONPATH="/home/whisper/stt-project/src"

LOG_DIR="/home/whisper/stt-project/logs/worker"
mkdir -p "${LOG_DIR}"

TIMESTAMP="$(date +%Y%m%d)"
LOG_FILE="${LOG_DIR}/celery_worker.log"
CONCURRENCY_COUNT=6

start_worker() {
  local gpu_id=$1
  local worker_name=$2

  CMD="CUDA_VISIBLE_DEVICES=${gpu_id} celery -A celery_app.app worker \
--loglevel=info \
--hostname=${worker_name}@$(hostname) \
--concurrency=${CONCURRENCY_COUNT} \
--logfile='${LOG_FILE}' "

  nohup bash -c "${CMD}" > /dev/null 2>&1 &
}

start_worker 0 worker0
start_worker 1 worker1
start_worker 2 worker2

