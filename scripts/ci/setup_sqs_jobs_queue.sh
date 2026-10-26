#!/usr/bin/env bash
# Create or update the SQS queue for background jobs (backend/jobs) and its
# dead-letter queue, and let the production EC2 instance role use them.
# Idempotent: safe to re-run.
#
#   smart-tutor-jobs      standard queue the API sends to and the worker reads
#   smart-tutor-jobs-dlq  where a job lands after MAX_RECEIVES failed attempts
#
# Both keep messages 14 days (the SQS maximum), so jobs queued while the
# instance is stopped overnight or over a weekend are still there at start.
#
# Env: INSTANCE_ID (required), AWS_REGION (default us-east-1),
#      QUEUE_NAME (default smart-tutor-jobs), MAX_RECEIVES (default 5),
#      VISIBILITY_TIMEOUT (default 900; the worker extends it for long jobs).
set -euo pipefail

: "${INSTANCE_ID:?INSTANCE_ID is required}"
REGION="${AWS_REGION:-us-east-1}"
QUEUE_NAME="${QUEUE_NAME:-smart-tutor-jobs}"
DLQ_NAME="${QUEUE_NAME}-dlq"
MAX_RECEIVES="${MAX_RECEIVES:-5}"
VISIBILITY_TIMEOUT="${VISIBILITY_TIMEOUT:-900}"
RETENTION=1209600   # 14 days
POLICY_NAME="smart-tutor-jobs-queue"

export AWS_DEFAULT_REGION="$REGION"

# Create the queue, or bring an existing one's attributes up to date.
# $1 queue name, $2 attributes JSON. Prints the queue URL.
upsert_queue() {
  local name="$1" attrs="$2" url
  if url="$(aws sqs get-queue-url --queue-name "$name" --query QueueUrl --output text 2>/dev/null)"; then
    aws sqs set-queue-attributes --queue-url "$url" --attributes "$attrs"
    echo "updated queue ${name}" >&2
  else
    url="$(aws sqs create-queue --queue-name "$name" --attributes "$attrs" --query QueueUrl --output text)"
    echo "created queue ${name}" >&2
  fi
  echo "$url"
}

queue_arn() {
  aws sqs get-queue-attributes --queue-url "$1" --attribute-names QueueArn --query Attributes.QueueArn --output text
}

# --- Queues -----------------------------------------------------------------
# SQS attribute values are strings, so the redrive policies are JSON encoded
# inside the attributes JSON; jq handles the quoting.
DLQ_URL="$(upsert_queue "$DLQ_NAME" "$(jq -nc --arg r "$RETENTION" \
  '{MessageRetentionPeriod: $r, SqsManagedSseEnabled: "true"}')")"
DLQ_ARN="$(queue_arn "$DLQ_URL")"

QUEUE_URL="$(upsert_queue "$QUEUE_NAME" "$(jq -nc \
  --arg v "$VISIBILITY_TIMEOUT" --arg r "$RETENTION" --arg dlq "$DLQ_ARN" --arg max "$MAX_RECEIVES" \
  '{VisibilityTimeout: $v, MessageRetentionPeriod: $r, ReceiveMessageWaitTimeSeconds: "20",
    SqsManagedSseEnabled: "true",
    RedrivePolicy: ({deadLetterTargetArn: $dlq, maxReceiveCount: $max} | tojson)}')")"
QUEUE_ARN="$(queue_arn "$QUEUE_URL")"

# Only the jobs queue may use this DLQ.
aws sqs set-queue-attributes --queue-url "$DLQ_URL" --attributes "$(jq -nc --arg src "$QUEUE_ARN" \
  '{RedriveAllowPolicy: ({redrivePermission: "byQueue", sourceQueueArns: [$src]} | tojson)}')"

# --- IAM: let the instance role send, receive and delete --------------------
POLICY="$(jq -nc --arg q "$QUEUE_ARN" --arg dlq "$DLQ_ARN" '{Version: "2012-10-17", Statement: [
  {Sid: "JobsQueue", Effect: "Allow", Resource: $q,
   Action: ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage",
            "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]},
  {Sid: "JobsDeadLetterQueue", Effect: "Allow", Resource: $dlq, Action: ["sqs:GetQueueAttributes"]}]}')"

PROFILE_ARN="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' --output text 2>/dev/null || true)"
if [ -n "$PROFILE_ARN" ] && [ "$PROFILE_ARN" != "None" ]; then
  PROFILE_NAME="${PROFILE_ARN##*/}"
  ROLE_NAME="$(aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" \
    --query 'InstanceProfile.Roles[0].RoleName' --output text)"
  aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "$POLICY_NAME" --policy-document "$POLICY"
  echo "attached ${POLICY_NAME} to instance role ${ROLE_NAME}"
else
  echo "::warning::${INSTANCE_ID} has no IAM instance profile, so no permissions were granted." \
    "If the backend uses AWS keys from ~/smart-tutor.env, attach this policy to that IAM user as ${POLICY_NAME}:"
  echo "$POLICY"
fi

# --- Result -----------------------------------------------------------------
echo ""
echo "JOBS_QUEUE_URL=${QUEUE_URL}"
echo "DLQ: ${DLQ_URL}"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "## Jobs queue"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| Queue URL | \`${QUEUE_URL}\` |"
    echo "| Dead-letter queue | \`${DLQ_URL}\` (after ${MAX_RECEIVES} attempts) |"
    echo ""
    echo "Set the repository variable \`JOBS_QUEUE_URL\` to the queue URL; the next production deploy starts the worker."
  } >> "$GITHUB_STEP_SUMMARY"
fi
