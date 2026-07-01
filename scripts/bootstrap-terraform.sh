#!/usr/bin/env bash
set -euo pipefail

BUCKET="${1:-agentops-terraform-state}"
TABLE="${2:-agentops-terraform-locks}"
REGION="${3:-us-east-1}"

echo "==> Creating S3 bucket: $BUCKET"
aws s3 mb "s3://$BUCKET" --region "$REGION" 2>/dev/null || echo "Bucket already exists"

echo "==> Enabling versioning on S3 bucket"
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

echo "==> Creating DynamoDB table: $TABLE"
aws dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null || echo "Table already exists"

echo "==> Done. Run: terraform -chdir=terraform init"
