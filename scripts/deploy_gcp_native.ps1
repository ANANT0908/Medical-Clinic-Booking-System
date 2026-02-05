# deploy_gcp_native.ps1
# Deploy to GCP using standard gcloud commands (No Terraform required)
# Prerequisites: gcloud CLI, Docker

param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectId
)

$Region = "us-central1"
$TopicName = "booking-events"
$DbInstance = "medical-booking-db"

Write-Host "Starting Native Deployment for Project: $ProjectId" -ForegroundColor Green

# 1. Configuration
gcloud config set project $ProjectId
gcloud config set run/region $Region

# 2. Enable APIs
Write-Host "Enabling APIs..." -ForegroundColor Cyan
gcloud services enable run.googleapis.com sql-component.googleapis.com pubsub.googleapis.com containerregistry.googleapis.com

# 3. Create Cloud SQL
Write-Host "Creating Cloud SQL Instance (this may take a few minutes)..." -ForegroundColor Cyan
# Check if exists to avoid error
$dbCheck = gcloud sql instances list --filter="name:$DbInstance" --format="value(name)"
if (-not $dbCheck) {
    gcloud sql instances create $DbInstance --database-version=POSTGRES_14 --tier=db-f1-micro --region=$Region --root-password=postgres
    gcloud sql databases create medical_booking_db --instance=$DbInstance
} else {
    Write-Host "Database instance already exists." -ForegroundColor Yellow
}

# 4. Create Pub/Sub Topic
Write-Host "Creating Pub/Sub Topic..." -ForegroundColor Cyan
$topicCheck = gcloud pubsub topics list --filter="name:projects/$ProjectId/topics/$TopicName" --format="value(name)"
if (-not $topicCheck) {
    gcloud pubsub topics create $TopicName
}

# 5. Build and Deploy Services
$Services = @("api-gateway", "validation-service", "pricing-service", "quota-manager", "booking-orchestrator")

# Configure Docker
gcloud auth configure-docker

foreach ($svc in $Services) {
    Write-Host "-------- Processing $svc --------" -ForegroundColor Cyan
    
    # Build & Push
    $ImageName = "gcr.io/$ProjectId/$svc`:latest"
    docker build -t $ImageName ".\services\$svc"
    docker push $ImageName
    
    # Deploy Cloud Run
    Write-Host "Deploying $svc to Cloud Run..."
    gcloud run deploy $svc `
        --image $ImageName `
        --platform managed `
        --region $Region `
        --allow-unauthenticated `
        --set-env-vars PROJECT_ID=$ProjectId,TOPIC_ID=$TopicName
}

# 6. Create Subscriptions
Write-Host "Creating Pub/Sub Subscriptions..." -ForegroundColor Cyan

# Helper to get URL
function Get-ServiceUrl ($s) {
    gcloud run services describe $s --format="value(status.url)"
}

# Validation Sub
$ValUrl = Get-ServiceUrl "validation-service"
gcloud pubsub subscriptions create validation-sub `
    --topic=$TopicName `
    --push-endpoint=$ValUrl `
    --message-filter='attributes.event_type = "booking.initiated"' `
    --quiet 2>$null

# Pricing Sub
$PriceUrl = Get-ServiceUrl "pricing-service"
gcloud pubsub subscriptions create pricing-sub `
    --topic=$TopicName `
    --push-endpoint=$PriceUrl `
    --message-filter='attributes.event_type = "booking.validated"' `
    --quiet 2>$null

# Quota Sub
$QuotaUrl = Get-ServiceUrl "quota-manager"
gcloud pubsub subscriptions create quota-sub `
    --topic=$TopicName `
    --push-endpoint=$QuotaUrl `
    --message-filter='attributes.event_type = "booking.priced" OR attributes.event_type = "booking.compensate"' `
    --quiet 2>$null

# Orchestrator Sub
$OrchUrl = Get-ServiceUrl "orchestrator" # Note: service name is 'orchestrator' in deploy loop? No, it's 'booking-orchestrator' folder but let's check deploy name
# In loop above, deploy name uses folder name. Folder is 'booking-orchestrator'.
# My previous Terraform used 'orchestrator'. Let's ensure consistency.
# In the loop: services/booking-orchestrator -> gcloud run deploy booking-orchestrator.
$OrchUrl = Get-ServiceUrl "booking-orchestrator"
gcloud pubsub subscriptions create orchestrator-sub `
    --topic=$TopicName `
    --push-endpoint=$OrchUrl `
    --quiet 2>$null

# Output API Gateway URL
$ApiGatewayUrl = Get-ServiceUrl "api-gateway"
Write-Host "`nDeployment Complete!" -ForegroundColor Green
Write-Host "API Gateway URL: $ApiGatewayUrl"
