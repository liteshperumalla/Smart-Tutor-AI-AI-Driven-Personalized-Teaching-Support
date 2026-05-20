#!/usr/bin/env bash
set -euo pipefail

# Resolve the production EC2 host before SSH-based workflows run.
#
# Inputs:
#   EC2_HOST                 Optional static public IP/DNS fallback.
#   EC2_INSTANCE_ID          Preferred AWS instance id.
#   EC2_INSTANCE_NAME        Optional Name tag fallback.
#   EC2_AUTO_START           true/false; starts stopped instances when possible.
#   EC2_TEMPORARY_SSH_INGRESS true/false; temporarily allow this runner on SSH.
#   AWS_REGION               AWS region for EC2 queries.
#
# Outputs:
#   Exports EC2_HOST and EC2_RESOLVED_* values through GITHUB_ENV when present.

AWS_REGION="${AWS_REGION:-us-east-1}"
EC2_HOST="${EC2_HOST:-}"
EC2_INSTANCE_ID="${EC2_INSTANCE_ID:-}"
EC2_INSTANCE_NAME="${EC2_INSTANCE_NAME:-}"
EC2_AUTO_START="$(printf '%s' "${EC2_AUTO_START:-true}" | tr '[:upper:]' '[:lower:]')"
EC2_TEMPORARY_SSH_INGRESS="$(printf '%s' "${EC2_TEMPORARY_SSH_INGRESS:-true}" | tr '[:upper:]' '[:lower:]')"

write_env() {
  local name="$1"
  local value="$2"
  if [ -n "${GITHUB_ENV:-}" ]; then
    printf '%s=%s\n' "${name}" "${value}" >> "${GITHUB_ENV}"
  fi
  export "${name}=${value}"
}

write_output() {
  local name="$1"
  local value="$2"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    printf '%s=%s\n' "${name}" "${value}" >> "${GITHUB_OUTPUT}"
  fi
}

mask_value() {
  local value="$1"
  if [ -n "${value}" ] && [ "${value}" != "None" ]; then
    echo "::add-mask::${value}"
  fi
}

if ! command -v aws >/dev/null 2>&1; then
  if [ -n "${EC2_HOST}" ]; then
    echo "::warning::AWS CLI is unavailable; using EC2_HOST as provided."
    write_env "EC2_HOST" "${EC2_HOST}"
    write_output "host" "${EC2_HOST}"
    exit 0
  fi

  echo "::error::AWS CLI is unavailable and EC2_HOST is not set."
  exit 1
fi

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  if [ -n "${EC2_HOST}" ]; then
    echo "::warning::AWS credentials are unavailable; using EC2_HOST as provided."
    write_env "EC2_HOST" "${EC2_HOST}"
    write_output "host" "${EC2_HOST}"
    exit 0
  fi

  echo "::error::AWS credentials are unavailable and EC2_HOST is not set."
  exit 1
fi

describe_instance() {
  if [ -n "${EC2_INSTANCE_ID}" ]; then
    aws ec2 describe-instances \
      --region "${AWS_REGION}" \
      --instance-ids "${EC2_INSTANCE_ID}" \
      --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PublicIpAddress,PrivateIpAddress,PublicDnsName,join(`,`,SecurityGroups[].GroupId)]' \
      --output text 2>/tmp/ec2-describe-error.log
    return
  fi

  if [ -n "${EC2_INSTANCE_NAME}" ]; then
    aws ec2 describe-instances \
      --region "${AWS_REGION}" \
      --filters \
        "Name=tag:Name,Values=${EC2_INSTANCE_NAME}" \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" \
      --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PublicIpAddress,PrivateIpAddress,PublicDnsName,join(`,`,SecurityGroups[].GroupId)]' \
      --output text 2>/tmp/ec2-describe-error.log
    return
  fi

  if [ -n "${EC2_HOST}" ]; then
    aws ec2 describe-instances \
      --region "${AWS_REGION}" \
      --filters \
        "Name=ip-address,Values=${EC2_HOST}" \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" \
      --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PublicIpAddress,PrivateIpAddress,PublicDnsName,join(`,`,SecurityGroups[].GroupId)]' \
      --output text 2>/tmp/ec2-describe-error.log
    return
  fi

  return 1
}

if ! instance_row="$(describe_instance)"; then
  if [ -s /tmp/ec2-describe-error.log ]; then
    cat /tmp/ec2-describe-error.log >&2
  fi
  if [ -n "${EC2_HOST}" ]; then
    echo "::warning::Could not resolve EC2 metadata; using EC2_HOST as provided."
    write_env "EC2_HOST" "${EC2_HOST}"
    write_output "host" "${EC2_HOST}"
    exit 0
  fi
  echo "::error::Could not resolve EC2 target. Set EC2_HOST or EC2_INSTANCE_ID."
  exit 1
fi

if [ -z "${instance_row}" ] || [ "${instance_row}" = "None" ]; then
  if [ -n "${EC2_HOST}" ]; then
    echo "::warning::No EC2 instance matched the configured selector; using EC2_HOST as provided."
    write_env "EC2_HOST" "${EC2_HOST}"
    write_output "host" "${EC2_HOST}"
    exit 0
  fi
  echo "::error::No EC2 instance matched the configured selector."
  exit 1
fi

read -r resolved_instance_id resolved_state public_ip private_ip public_dns security_group_ids <<< "${instance_row}"
public_ip="${public_ip/None/}"
private_ip="${private_ip/None/}"
public_dns="${public_dns/None/}"
security_group_ids="${security_group_ids/None/}"

cold_start=false
if [ "${resolved_state}" = "stopped" ]; then
  if [ "${EC2_AUTO_START}" = "true" ]; then
    echo "Production EC2 instance is stopped; starting it before workflow SSH."
    aws ec2 start-instances --region "${AWS_REGION}" --instance-ids "${resolved_instance_id}" >/dev/null
    aws ec2 wait instance-running --region "${AWS_REGION}" --instance-ids "${resolved_instance_id}"
    cold_start=true
    instance_row="$(EC2_INSTANCE_ID="${resolved_instance_id}" describe_instance)"
    read -r resolved_instance_id resolved_state public_ip private_ip public_dns security_group_ids <<< "${instance_row}"
    public_ip="${public_ip/None/}"
    private_ip="${private_ip/None/}"
    public_dns="${public_dns/None/}"
    security_group_ids="${security_group_ids/None/}"
  else
    echo "::error::Production EC2 instance is stopped. Set EC2_AUTO_START=true or start it manually."
    exit 1
  fi
fi

if [ "${resolved_state}" != "running" ]; then
  echo "::error::Production EC2 instance is not running. Current state: ${resolved_state}"
  exit 1
fi

resolved_host="${public_ip:-${public_dns:-${EC2_HOST}}}"
if [ -z "${resolved_host}" ]; then
  echo "::error::Resolved EC2 instance is running but has no public host."
  exit 1
fi

mask_value "${resolved_host}"
mask_value "${public_ip}"
mask_value "${private_ip}"
mask_value "${public_dns}"

write_env "EC2_HOST" "${resolved_host}"
write_env "EC2_RESOLVED_INSTANCE_ID" "${resolved_instance_id}"
write_env "EC2_RESOLVED_STATE" "${resolved_state}"
write_env "EC2_RESOLVED_PUBLIC_IP" "${public_ip}"
write_env "EC2_RESOLVED_PRIVATE_IP" "${private_ip}"
write_env "EC2_RESOLVED_SECURITY_GROUP_IDS" "${security_group_ids}"
write_output "host" "${resolved_host}"
write_output "instance_id" "${resolved_instance_id}"
write_output "state" "${resolved_state}"

if [ "${EC2_TEMPORARY_SSH_INGRESS}" = "true" ] && [ -n "${security_group_ids}" ]; then
  if command -v curl >/dev/null 2>&1 && runner_ip="$(curl -fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')"; then
    if [[ "${runner_ip}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      runner_cidr="${runner_ip}/32"
      mask_value "${runner_cidr}"
      for group_id in ${security_group_ids//,/ }; do
        if aws ec2 authorize-security-group-ingress \
          --region "${AWS_REGION}" \
          --group-id "${group_id}" \
          --protocol tcp \
          --port 22 \
          --cidr "${runner_cidr}" >/tmp/ec2-authorize-ssh.log 2>&1; then
          echo "Temporarily authorized this GitHub runner for SSH."
        elif grep -q "InvalidPermission.Duplicate" /tmp/ec2-authorize-ssh.log; then
          echo "Temporary SSH ingress already exists for this GitHub runner."
        else
          cat /tmp/ec2-authorize-ssh.log >&2
          echo "::warning::Unable to add temporary SSH ingress to ${group_id}; SSH may still fail."
        fi
      done
      write_env "EC2_TEMP_SSH_CIDR" "${runner_cidr}"
      write_env "EC2_TEMP_SSH_SECURITY_GROUP_IDS" "${security_group_ids}"
    else
      echo "::warning::Could not determine a valid GitHub runner IPv4 address for temporary SSH ingress."
    fi
  else
    echo "::warning::Could not determine GitHub runner public IP for temporary SSH ingress."
  fi
fi

# Wait for SSH daemon to actually accept TCP connections.
# `aws ec2 wait instance-running` only confirms the lifecycle state; the OS
# still needs time to boot and start sshd. On cold starts this is typically
# 30–90s, and stale ARP/route entries on shared GitHub runners can extend it.
SSH_READY_TIMEOUT_SECONDS="${SSH_READY_TIMEOUT_SECONDS:-240}"
SSH_READY_INTERVAL_SECONDS="${SSH_READY_INTERVAL_SECONDS:-5}"
if [ "${cold_start}" = "true" ]; then
  SSH_READY_TIMEOUT_SECONDS="${SSH_READY_COLD_TIMEOUT_SECONDS:-360}"
fi

probe_ssh_port() {
  local host="$1"
  local port="${2:-22}"
  if command -v nc >/dev/null 2>&1; then
    nc -z -w 5 "${host}" "${port}" >/dev/null 2>&1
    return $?
  fi
  (exec 3<>"/dev/tcp/${host}/${port}") >/dev/null 2>&1 && {
    exec 3<&-
    exec 3>&-
    return 0
  }
  return 1
}

echo "Waiting for SSH on ${resolved_host}:22 (timeout ${SSH_READY_TIMEOUT_SECONDS}s)..."
deadline=$(( $(date +%s) + SSH_READY_TIMEOUT_SECONDS ))
attempt=0
until probe_ssh_port "${resolved_host}" 22; do
  attempt=$((attempt + 1))
  if [ "$(date +%s)" -ge "${deadline}" ]; then
    echo "::error::SSH port 22 on ${resolved_host} did not become ready within ${SSH_READY_TIMEOUT_SECONDS}s after ${attempt} probes."
    exit 1
  fi
  sleep "${SSH_READY_INTERVAL_SECONDS}"
done
echo "SSH port 22 is accepting connections on ${resolved_host} (after ${attempt} probes)."

echo "Resolved production EC2 target from AWS metadata."
