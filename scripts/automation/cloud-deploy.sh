#!/bin/bash

# Cloud Deployment Script for AI Shopping Concierge
# Supports AWS ECS, Google Cloud Run, and Azure Container Instances

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
DEPLOYMENT_CONFIG="$PROJECT_DIR/deployment/cloud-config.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load configuration
if [[ -f "$DEPLOYMENT_CONFIG" ]]; then
    source "$DEPLOYMENT_CONFIG"
    log_info "Loaded configuration from $DEPLOYMENT_CONFIG"
else
    log_warning "No configuration file found at $DEPLOYMENT_CONFIG"
    log_info "Using default configuration values"
fi

# Default values
CLOUD_PROVIDER=${CLOUD_PROVIDER:-"aws"}
REGION=${REGION:-"us-west-2"}
PROJECT_NAME=${PROJECT_NAME:-"ai-shopping-concierge"}
ENVIRONMENT=${ENVIRONMENT:-"production"}
IMAGE_TAG=${IMAGE_TAG:-"latest"}
DOMAIN_NAME=${DOMAIN_NAME:-""}

# Display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

Cloud deployment script for AI Shopping Concierge

Commands:
    deploy          Deploy to cloud platform
    destroy         Remove deployment from cloud platform
    status          Check deployment status
    logs            View application logs
    scale           Scale the deployment
    update          Update the deployment with new image
    rollback        Rollback to previous deployment

Options:
    -p, --provider  Cloud provider (aws|gcp|azure) [default: aws]
    -r, --region    Deployment region [default: us-west-2]
    -e, --env       Environment (dev|staging|production) [default: production]
    -t, --tag       Docker image tag [default: latest]
    -d, --domain    Domain name for the service
    -h, --help      Show this help message

Examples:
    $0 deploy
    $0 --provider gcp --region us-central1 deploy
    $0 --env staging scale 5
    $0 --tag v1.2.3 update
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--provider)
                CLOUD_PROVIDER="$2"
                shift 2
                ;;
            -r|--region)
                REGION="$2"
                shift 2
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -d|--domain)
                DOMAIN_NAME="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            deploy|destroy|status|logs|scale|update|rollback)
                COMMAND="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for $CLOUD_PROVIDER deployment..."
    
    case $CLOUD_PROVIDER in
        aws)
            if ! command -v aws &> /dev/null; then
                log_error "AWS CLI not found. Please install AWS CLI."
                exit 1
            fi
            if ! command -v ecs-cli &> /dev/null; then
                log_warning "ECS CLI not found. Some features may not be available."
            fi
            ;;
        gcp)
            if ! command -v gcloud &> /dev/null; then
                log_error "Google Cloud CLI not found. Please install gcloud."
                exit 1
            fi
            ;;
        azure)
            if ! command -v az &> /dev/null; then
                log_error "Azure CLI not found. Please install Azure CLI."
                exit 1
            fi
            ;;
        *)
            log_error "Unsupported cloud provider: $CLOUD_PROVIDER"
            exit 1
            ;;
    esac
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building and pushing Docker image..."
    
    local image_name="$PROJECT_NAME:$IMAGE_TAG"
    local registry_url
    
    case $CLOUD_PROVIDER in
        aws)
            # Get AWS account ID and ECR registry URL
            local aws_account_id=$(aws sts get-caller-identity --query Account --output text)
            registry_url="$aws_account_id.dkr.ecr.$REGION.amazonaws.com"
            
            # Create ECR repository if it doesn't exist
            aws ecr describe-repositories --repository-names "$PROJECT_NAME" --region "$REGION" &>/dev/null || \
                aws ecr create-repository --repository-name "$PROJECT_NAME" --region "$REGION"
            
            # Get ECR login token
            aws ecr get-login-password --region "$REGION" | \
                docker login --username AWS --password-stdin "$registry_url"
            ;;
        gcp)
            # Set up Google Container Registry
            registry_url="gcr.io/$(gcloud config get-value project)"
            gcloud auth configure-docker --quiet
            ;;
        azure)
            # Set up Azure Container Registry
            local acr_name="${PROJECT_NAME//-/}acr"
            registry_url="$acr_name.azurecr.io"
            
            # Create ACR if it doesn't exist
            az acr show --name "$acr_name" --resource-group "$PROJECT_NAME-rg" &>/dev/null || \
                az acr create --name "$acr_name" --resource-group "$PROJECT_NAME-rg" --sku Basic
            
            az acr login --name "$acr_name"
            ;;
    esac
    
    local full_image_name="$registry_url/$image_name"
    
    # Build and push image
    docker build -t "$image_name" -t "$full_image_name" "$PROJECT_DIR"
    docker push "$full_image_name"
    
    log_success "Image pushed to $full_image_name"
    echo "$full_image_name"
}

# Deploy to AWS ECS
deploy_aws() {
    log_info "Deploying to AWS ECS..."
    
    local image_url=$(build_and_push_image)
    local cluster_name="$PROJECT_NAME-$ENVIRONMENT"
    local service_name="$PROJECT_NAME-service"
    local task_family="$PROJECT_NAME-task"
    
    # Create ECS cluster
    aws ecs create-cluster --cluster-name "$cluster_name" --region "$REGION" &>/dev/null || true
    
    # Create task definition
    local task_definition=$(cat << EOF
{
    "family": "$task_family",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "executionRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskRole",
    "containerDefinitions": [
        {
            "name": "$PROJECT_NAME",
            "image": "$image_url",
            "portMappings": [
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {"name": "ENVIRONMENT", "value": "$ENVIRONMENT"},
                {"name": "DEBUG", "value": "false"}
            ],
            "secrets": [
                {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:$REGION:$(aws sts get-caller-identity --query Account --output text):secret:$PROJECT_NAME-db-url"},
                {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:$REGION:$(aws sts get-caller-identity --query Account --output text):secret:$PROJECT_NAME-redis-url"}
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/$PROJECT_NAME",
                    "awslogs-region": "$REGION",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }
    ]
}
EOF
)
    
    # Register task definition
    aws ecs register-task-definition --cli-input-json "$task_definition" --region "$REGION"
    
    # Create or update service
    local service_exists=$(aws ecs describe-services --cluster "$cluster_name" --services "$service_name" --region "$REGION" --query 'services[0].status' --output text 2>/dev/null)
    
    if [[ "$service_exists" != "None" && "$service_exists" != "" ]]; then
        log_info "Updating existing ECS service..."
        aws ecs update-service \
            --cluster "$cluster_name" \
            --service "$service_name" \
            --task-definition "$task_family" \
            --region "$REGION"
    else
        log_info "Creating new ECS service..."
        aws ecs create-service \
            --cluster "$cluster_name" \
            --service-name "$service_name" \
            --task-definition "$task_family" \
            --desired-count 2 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-12345],assignPublicIp=ENABLED}" \
            --region "$REGION"
    fi
    
    log_success "AWS ECS deployment completed"
}

# Deploy to Google Cloud Run
deploy_gcp() {
    log_info "Deploying to Google Cloud Run..."
    
    local image_url=$(build_and_push_image)
    local service_name="$PROJECT_NAME-$ENVIRONMENT"
    
    # Deploy to Cloud Run
    gcloud run deploy "$service_name" \
        --image "$image_url" \
        --platform managed \
        --region "$REGION" \
        --allow-unauthenticated \
        --port 8000 \
        --memory 2Gi \
        --cpu 2 \
        --max-instances 10 \
        --set-env-vars "ENVIRONMENT=$ENVIRONMENT,DEBUG=false" \
        --quiet
    
    # Get service URL
    local service_url=$(gcloud run services describe "$service_name" --region "$REGION" --format 'value(status.url)')
    
    log_success "Google Cloud Run deployment completed"
    log_info "Service URL: $service_url"
}

# Deploy to Azure Container Instances
deploy_azure() {
    log_info "Deploying to Azure Container Instances..."
    
    local image_url=$(build_and_push_image)
    local resource_group="$PROJECT_NAME-rg"
    local container_name="$PROJECT_NAME-$ENVIRONMENT"
    
    # Create resource group
    az group create --name "$resource_group" --location "$REGION" &>/dev/null || true
    
    # Deploy container
    az container create \
        --resource-group "$resource_group" \
        --name "$container_name" \
        --image "$image_url" \
        --cpu 2 \
        --memory 4 \
        --ports 8000 \
        --environment-variables "ENVIRONMENT=$ENVIRONMENT" "DEBUG=false" \
        --restart-policy Always \
        --location "$REGION"
    
    # Get container IP
    local container_ip=$(az container show --resource-group "$resource_group" --name "$container_name" --query 'ipAddress.ip' --output tsv)
    
    log_success "Azure Container Instances deployment completed"
    log_info "Container IP: $container_ip"
}

# Main deployment function
deploy() {
    check_prerequisites
    
    case $CLOUD_PROVIDER in
        aws)
            deploy_aws
            ;;
        gcp)
            deploy_gcp
            ;;
        azure)
            deploy_azure
            ;;
    esac
}

# Destroy deployment
destroy() {
    log_info "Destroying $CLOUD_PROVIDER deployment..."
    
    case $CLOUD_PROVIDER in
        aws)
            local cluster_name="$PROJECT_NAME-$ENVIRONMENT"
            local service_name="$PROJECT_NAME-service"
            
            # Delete ECS service
            aws ecs update-service --cluster "$cluster_name" --service "$service_name" --desired-count 0 --region "$REGION" || true
            aws ecs delete-service --cluster "$cluster_name" --service "$service_name" --region "$REGION" || true
            
            # Delete ECS cluster
            aws ecs delete-cluster --cluster "$cluster_name" --region "$REGION" || true
            ;;
        gcp)
            local service_name="$PROJECT_NAME-$ENVIRONMENT"
            gcloud run services delete "$service_name" --region "$REGION" --quiet || true
            ;;
        azure)
            local resource_group="$PROJECT_NAME-rg"
            az group delete --name "$resource_group" --yes --no-wait || true
            ;;
    esac
    
    log_success "Deployment destroyed"
}

# Check deployment status
status() {
    log_info "Checking deployment status on $CLOUD_PROVIDER..."
    
    case $CLOUD_PROVIDER in
        aws)
            local cluster_name="$PROJECT_NAME-$ENVIRONMENT"
            local service_name="$PROJECT_NAME-service"
            aws ecs describe-services --cluster "$cluster_name" --services "$service_name" --region "$REGION"
            ;;
        gcp)
            local service_name="$PROJECT_NAME-$ENVIRONMENT"
            gcloud run services describe "$service_name" --region "$REGION"
            ;;
        azure)
            local resource_group="$PROJECT_NAME-rg"
            local container_name="$PROJECT_NAME-$ENVIRONMENT"
            az container show --resource-group "$resource_group" --name "$container_name"
            ;;
    esac
}

# View logs
logs() {
    log_info "Fetching logs from $CLOUD_PROVIDER..."
    
    case $CLOUD_PROVIDER in
        aws)
            local log_group="/ecs/$PROJECT_NAME"
            aws logs tail "$log_group" --follow --region "$REGION"
            ;;
        gcp)
            local service_name="$PROJECT_NAME-$ENVIRONMENT"
            gcloud logs tail "resource.type=cloud_run_revision AND resource.labels.service_name=$service_name" --location "$REGION"
            ;;
        azure)
            local resource_group="$PROJECT_NAME-rg"
            local container_name="$PROJECT_NAME-$ENVIRONMENT"
            az container logs --resource-group "$resource_group" --name "$container_name" --follow
            ;;
    esac
}

# Scale deployment
scale() {
    local replicas=${1:-2}
    log_info "Scaling deployment to $replicas replicas on $CLOUD_PROVIDER..."
    
    case $CLOUD_PROVIDER in
        aws)
            local cluster_name="$PROJECT_NAME-$ENVIRONMENT"
            local service_name="$PROJECT_NAME-service"
            aws ecs update-service --cluster "$cluster_name" --service "$service_name" --desired-count "$replicas" --region "$REGION"
            ;;
        gcp)
            local service_name="$PROJECT_NAME-$ENVIRONMENT"
            gcloud run services update "$service_name" --region "$REGION" --max-instances "$replicas"
            ;;
        azure)
            log_warning "Azure Container Instances doesn't support auto-scaling. Manual recreation required."
            ;;
    esac
    
    log_success "Scaling completed"
}

# Update deployment
update() {
    log_info "Updating deployment with new image tag: $IMAGE_TAG"
    deploy
}

# Rollback deployment
rollback() {
    log_info "Rolling back deployment on $CLOUD_PROVIDER..."
    
    case $CLOUD_PROVIDER in
        aws)
            local cluster_name="$PROJECT_NAME-$ENVIRONMENT"
            local service_name="$PROJECT_NAME-service"
            local previous_task_def=$(aws ecs list-task-definitions --family-prefix "$PROJECT_NAME-task" --status ACTIVE --sort DESC --region "$REGION" --query 'taskDefinitionArns[1]' --output text)
            
            if [[ -n "$previous_task_def" ]]; then
                aws ecs update-service --cluster "$cluster_name" --service "$service_name" --task-definition "$previous_task_def" --region "$REGION"
                log_success "Rollback completed"
            else
                log_error "No previous task definition found"
            fi
            ;;
        gcp)
            local service_name="$PROJECT_NAME-$ENVIRONMENT"
            local previous_revision=$(gcloud run revisions list --service "$service_name" --region "$REGION" --limit 2 --sort-by "~metadata.creationTimestamp" --format "value(metadata.name)" | tail -n 1)
            
            if [[ -n "$previous_revision" ]]; then
                gcloud run services update-traffic "$service_name" --to-revisions "$previous_revision=100" --region "$REGION"
                log_success "Rollback completed"
            else
                log_error "No previous revision found"
            fi
            ;;
        azure)
            log_warning "Azure Container Instances doesn't support rollback. Manual deployment required."
            ;;
    esac
}

# Main script execution
main() {
    parse_args "$@"
    
    if [[ -z "$COMMAND" ]]; then
        log_error "No command specified"
        usage
        exit 1
    fi
    
    case $COMMAND in
        deploy)
            deploy
            ;;
        destroy)
            destroy
            ;;
        status)
            status
            ;;
        logs)
            logs
            ;;
        scale)
            scale "$2"
            ;;
        update)
            update
            ;;
        rollback)
            rollback
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"