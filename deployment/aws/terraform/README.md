# Terraform scope

Provision these AWS resources through approved Terraform modules or your organization's landing-zone templates:

- EKS cluster with private subnets across at least three Availability Zones.
- Three ECR repositories: `job-service`, `processor-service`, `audit-service`.
- Amazon MQ RabbitMQ cluster deployment, not a single broker.
- ElastiCache Redis replication group with encryption in transit and at rest.
- ACM certificate, Cognito user pool/app client, and AWS Load Balancer Controller IAM role.
- GitHub OIDC IAM role restricted by the repository and `main` branch subject claim.

Network endpoints for Amazon MQ and ElastiCache must remain private. Inject their connection strings from AWS Secrets Manager; never place credentials in Terraform state or Kubernetes YAML.
