#!/usr/bin/env bash
# Create or update the EventBridge Scheduler schedules that start and stop
# the production EC2 instance. Idempotent: safe to re-run.
#
# Why: GitHub cron (ec2-schedule.yml) is best effort and has missed the
# 09:00 start by over an hour. EventBridge Scheduler fires on time and
# understands America/Chicago, so DST needs no separate entries.
#
#   start  Mon-Fri 08:50 Chicago   so the app is up before 09:00
#   stop   Mon-Fri 17:30 Chicago   backstop only; ec2-schedule.yml stops at
#                                  17:00 unless a deploy is running, and
#                                  this catches the days its cron misses
#
# Env: INSTANCE_ID (required), AWS_REGION (default us-east-1),
#      SCHEDULE_TZ (default America/Chicago), START_CRON, STOP_CRON.
set -euo pipefail

: "${INSTANCE_ID:?INSTANCE_ID is required}"
REGION="${AWS_REGION:-us-east-1}"
TZ_NAME="${SCHEDULE_TZ:-America/Chicago}"
START_CRON="${START_CRON:-cron(50 8 ? * MON-FRI *)}"
STOP_CRON="${STOP_CRON:-cron(30 17 ? * MON-FRI *)}"
GROUP="smart-tutor"
ROLE_NAME="smart-tutor-ec2-scheduler"

export AWS_DEFAULT_REGION="$REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
INSTANCE_ARN="arn:aws:ec2:${REGION}:${ACCOUNT_ID}:instance/${INSTANCE_ID}"

# --- IAM role the scheduler assumes to call ec2:Start/StopInstances --------
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole","Condition":{"StringEquals":{"aws:SourceAccount":"'"$ACCOUNT_ID"'"}}}]}'
POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ec2:StartInstances","ec2:StopInstances"],"Resource":"'"$INSTANCE_ARN"'"}]}'

if ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text 2>/dev/null)"; then
  echo "IAM role exists: $ROLE_ARN"
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$TRUST"
else
  ROLE_ARN="$(aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST" \
    --description "EventBridge Scheduler: start/stop Smart AI Tutor EC2" \
    --query Role.Arn --output text)"
  echo "Created IAM role: $ROLE_ARN"
  # New roles take a few seconds before the scheduler can assume them.
  sleep 10
fi
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name ec2-start-stop --policy-document "$POLICY"

# --- Schedule group ---------------------------------------------------------
aws scheduler get-schedule-group --name "$GROUP" >/dev/null 2>&1 \
  || aws scheduler create-schedule-group --name "$GROUP" >/dev/null

# --- Schedules --------------------------------------------------------------
upsert() {
  local name="$1" expr="$2" api="$3" desc="$4"
  local target
  target="$(printf '{"Arn":"arn:aws:scheduler:::aws-sdk:ec2:%s","RoleArn":"%s","Input":"{\\"InstanceIds\\":[\\"%s\\"]}","RetryPolicy":{"MaximumRetryAttempts":3,"MaximumEventAgeInSeconds":900}}' "$api" "$ROLE_ARN" "$INSTANCE_ID")"
  local verb=create-schedule
  aws scheduler get-schedule --group-name "$GROUP" --name "$name" >/dev/null 2>&1 && verb=update-schedule
  aws scheduler "$verb" --group-name "$GROUP" --name "$name" \
    --schedule-expression "$expr" --schedule-expression-timezone "$TZ_NAME" \
    --flexible-time-window Mode=OFF --state ENABLED \
    --description "$desc" --target "$target" >/dev/null
  echo "${verb%-schedule}d ${GROUP}/${name}: ${expr} ${TZ_NAME} -> ec2:${api}"
}

upsert ec2-start "$START_CRON" startInstances "Start Smart AI Tutor EC2 before business hours"
upsert ec2-stop  "$STOP_CRON"  stopInstances  "Backstop stop for Smart AI Tutor EC2 after business hours"

aws scheduler list-schedules --group-name "$GROUP" \
  --query 'Schedules[].{name:Name,state:State}' --output table
