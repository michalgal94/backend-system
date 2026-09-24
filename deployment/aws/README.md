# AWS production deployment blueprint

This directory is intentionally deploy-ready configuration, not evidence of a live AWS deployment. Local development continues to use Uvicorn or Docker Compose.

## Target architecture

- Amazon EKS runs Job Service, Processor Service and Audit Service.
- Amazon ECR stores one immutable image per service.
- An AWS Application Load Balancer routes public traffic only to Job Service.
- Amazon Cognito authenticates users at the ALB; authorization policies are configured through Cognito groups and Kubernetes/AWS IAM permissions.
- Amazon MQ for RabbitMQ provides durable work/event queues. Use an HA cluster deployment across three Availability Zones.
- Amazon ElastiCache for Redis provides shared idempotency keys and WebSocket pub/sub coordination between Job Service replicas.

## Before deployment

1. Create an EKS cluster, private subnets, an ECR repository per service, an ACM certificate, Cognito user pool/app client, Amazon MQ RabbitMQ cluster and ElastiCache Redis replication group.
2. Install the AWS Load Balancer Controller and External Secrets Operator in EKS.
3. Create a GitHub OIDC IAM role restricted to this repository and the `main` branch. Do not store long-lived AWS access keys in GitHub secrets.
4. Copy `k8s/secrets.example.yaml` to a secret-management workflow such as AWS Secrets Manager plus External Secrets; never commit real values.
5. Replace all `REPLACE_*` values, apply the Kubernetes manifests, then configure the GitHub deployment environment with the EKS cluster and ECR repository names.

## Important limitation

The current assignment implementation deliberately retains REST/WebSocket processing and in-memory repositories for easy local execution. RabbitMQ, Redis, Cognito and EKS artifacts here are a production migration blueprint; enabling multi-replica Job Service safely also requires moving job state from the in-memory repository to persistent shared storage.
