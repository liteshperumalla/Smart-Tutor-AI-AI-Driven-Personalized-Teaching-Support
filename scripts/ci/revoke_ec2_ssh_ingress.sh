#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
cidr="${EC2_TEMP_SSH_CIDR:-}"
security_group_ids="${EC2_TEMP_SSH_SECURITY_GROUP_IDS:-}"

if [ -z "${cidr}" ] || [ -z "${security_group_ids}" ]; then
  echo "No temporary EC2 SSH ingress rule recorded; nothing to revoke."
  exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "::warning::AWS CLI is unavailable; cannot revoke temporary SSH ingress."
  exit 0
fi

for group_id in ${security_group_ids//,/ }; do
  if aws ec2 revoke-security-group-ingress \
    --region "${AWS_REGION}" \
    --group-id "${group_id}" \
    --protocol tcp \
    --port 22 \
    --cidr "${cidr}" >/tmp/ec2-revoke-ssh.log 2>&1; then
    echo "Revoked temporary SSH ingress from ${group_id}."
  elif grep -Eq "InvalidPermission.NotFound|InvalidPermission.Malformed" /tmp/ec2-revoke-ssh.log; then
    echo "Temporary SSH ingress was already absent from ${group_id}."
  else
    cat /tmp/ec2-revoke-ssh.log >&2
    echo "::warning::Unable to revoke temporary SSH ingress from ${group_id}."
  fi
done
