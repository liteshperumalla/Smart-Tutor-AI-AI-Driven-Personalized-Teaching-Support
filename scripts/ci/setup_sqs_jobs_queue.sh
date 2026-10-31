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
# The instance is found the way deploy-production.yml finds it (an instance
# id, else its Name tag, else its public IP), but read-only: this script
# never starts the instance or opens SSH.
#
# Env: EC2_INSTANCE_ID, EC2_INSTANCE_NAME or EC2_HOST (at least one),
#      AWS_REGION (default us-east-1), QUEUE_NAME (default smart-tutor-jobs),
#      MAX_RECEIVES (default 5),
#      VISIBILITY_TIMEOUT (default 900; the worker extends it for long jobs).
set -euo pipefail
# Fail inside $(...) too, or a failed AWS call there would be ignored.
shopt -s inherit_errexit

REGION="${AWS_REGION:-us-east-1}"
QUEUE_NAME="${QUEUE_NAME:-smart-tutor-jobs}"
DLQ_NAME="${QUEUE_NAME}-dlq"
MAX_RECEIVES="${MAX_RECEIVES:-5}"
VISIBILITY_TIMEOUT="${VISIBILITY_TIMEOUT:-900}"
RETENTION=1209600   # 14 days
POLICY_NAME="smart-tutor-jobs-queue"

export AWS_DEFAULT_REGION="$REGION"
AWS_ERR="$(mktemp)"
trap 'rm -f "$AWS_ERR"' EXIT

# Run the AWS CLI; on failure, report which call failed and AWS's message as
# an annotation, so the run summary says why without opening the log.
aws_call() {
  local rc=0
  aws "$@" 2>"$AWS_ERR" || rc=$?
  if [ "$rc" -ne 0 ]; then
    # stderr: callers capture stdout. The runner reads annotations from both.
    echo "::error title=aws $1 $2 failed (exit ${rc})::$(tr '\n' ' ' < "$AWS_ERR" | cut -c1-600)" >&2
    cat "$AWS_ERR" >&2
  fi
  return "$rc"
}

# --- Production instance ------------------------------------------------------
describe_instance() {
  local query='Reservations[0].Instances[0].[InstanceId,IamInstanceProfile.Arn]'
  if [ -n "${EC2_INSTANCE_ID:-}" ]; then
    aws_call ec2 describe-instances --instance-ids "$EC2_INSTANCE_ID" --query "$query" --output text
  elif [ -n "${EC2_INSTANCE_NAME:-}" ]; then
    aws_call ec2 describe-instances --query "$query" --output text \
      --filters "Name=tag:Name,Values=${EC2_INSTANCE_NAME}" \
                "Name=instance-state-name,Values=pending,running,stopping,stopped"
  elif [ -n "${EC2_HOST:-}" ]; then
    aws_call ec2 describe-instances --query "$query" --output text \
      --filters "Name=ip-address,Values=${EC2_HOST}" \
                "Name=instance-state-name,Values=pending,running,stopping,stopped"
  else
    echo "::error::Set EC2_INSTANCE_ID, EC2_INSTANCE_NAME or EC2_HOST (as for Production Deploy)." >&2
    return 1
  fi
}

INSTANCE_ROW="$(describe_instance)"
read -r INSTANCE_ID PROFILE_ARN <<< "$INSTANCE_ROW"
if [ -z "${INSTANCE_ID:-}" ] || [ "$INSTANCE_ID" = "None" ]; then
  echo "::error::No EC2 instance matched the configured EC2_INSTANCE_ID / EC2_INSTANCE_NAME / EC2_HOST."
  exit 1
fi
echo "production instance: ${INSTANCE_ID}"

# --- Queues -----------------------------------------------------------------
# Create the queue, or bring an existing one's attributes up to date.
# $1 queue name, $2 attributes JSON. Prints the queue URL.
upsert_queue() {
  local name="$1" attrs="$2" url rc=0
  url="$(aws sqs get-queue-url --queue-name "$name" --query QueueUrl --output text 2>"$AWS_ERR")" || rc=$?
  if [ "$rc" -eq 0 ]; then
    aws_call sqs set-queue-attributes --queue-url "$url" --attributes "$attrs"
    echo "updated queue ${name}" >&2
  elif grep -q "NonExistentQueue\|QueueDoesNotExist" "$AWS_ERR"; then
    url="$(aws_call sqs create-queue --queue-name "$name" --attributes "$attrs" --query QueueUrl --output text)"
    echo "created queue ${name}" >&2
  else
    # Anything but "doesn't exist" (AccessDenied, wrong region...) is fatal.
    echo "::error title=aws sqs get-queue-url failed (exit ${rc})::$(tr '\n' ' ' < "$AWS_ERR" | cut -c1-600)" >&2
    cat "$AWS_ERR" >&2
    return "$rc"
  fi
  echo "$url"
}

queue_arn() {
  aws_call sqs get-queue-attributes --queue-url "$1" --attribute-names QueueArn \
    --query Attributes.QueueArn --output text
}

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
aws_call sqs set-queue-attributes --queue-url "$DLQ_URL" --attributes "$(jq -nc --arg src "$QUEUE_ARN" \
  '{RedriveAllowPolicy: ({redrivePermission: "byQueue", sourceQueueArns: [$src]} | tojson)}')"

# --- IAM: let the instance role send, receive and delete --------------------
POLICY="$(jq -nc --arg q "$QUEUE_ARN" --arg dlq "$DLQ_ARN" '{Version: "2012-10-17", Statement: [
  {Sid: "JobsQueue", Effect: "Allow", Resource: $q,
   Action: ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage",
            "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]},
  {Sid: "JobsDeadLetterQueue", Effect: "Allow", Resource: $dlq, Action: ["sqs:GetQueueAttributes"]}]}')"

if [ -n "${PROFILE_ARN:-}" ] && [ "$PROFILE_ARN" != "None" ]; then
  PROFILE_NAME="${PROFILE_ARN##*/}"
  ROLE_NAME="$(aws_call iam get-instance-profile --instance-profile-name "$PROFILE_NAME" \
    --query 'InstanceProfile.Roles[0].RoleName' --output text)"
  aws_call iam put-role-policy --role-name "$ROLE_NAME" --policy-name "$POLICY_NAME" --policy-document "$POLICY"
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
    echo "| Instance | \`${INSTANCE_ID}\` |"
    echo ""
    echo "Set the repository variable \`JOBS_QUEUE_URL\` to the queue URL; the next production deploy starts the worker."
  } >> "$GITHUB_STEP_SUMMARY"
fi
