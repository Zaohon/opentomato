# fls-web CI/CD (dev only)

## Required GitLab variables

- `ACR_REGISTRY` (example: `fls-acr-registry-vpc.eu-central-1.cr.aliyuncs.com`)
- `ACR_IMAGE_REPO` (example: `apps/fls-web`)
- `ACR_USERNAME`
- `ACR_PASSWORD`
- `KUBECONFIG_B64_DEV` (preferred) or `KUBECONFIG_B64`

## Runner requirement

- Runner tag: `ack` (or change `default.tags` in `.gitlab-ci.yml`).

## AWS EKS pilot variables

- `AWS_REGION=eu-central-1`
- `AWS_ECR_REGISTRY=041492853875.dkr.ecr.eu-central-1.amazonaws.com`
- `AWS_ECR_REPOSITORY=fls/fls-web`
- `AWS_DEV_NAMESPACE=fls-dev`
- `AWS_INGRESS_HOST=agent-aws-dev.felicitysolar-shanghai.com`
- `AWS_ALB_CERT_ARN` defaults to the issued ACM certificate for `agent-aws-dev.felicitysolar-shanghai.com` in `.gitlab-ci.yml`

## AWS runner requirement

- Runner tag: `aws-dev-eks`
- Runner service account should assume the IRSA role `GitLabRunnerRole-fls-dev-eks`
- AWS pilot jobs auto-run on `develop`

## Branch policy

- `develop` branch triggers verify/build/deploy/smoke for dev.
