# deploy_gcp.ps1
# Usage: .\scripts\deploy_gcp.ps1 -ProjectId "your-project-id"

param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectId
)

$Region = "us-central1"

Write-Host "Starting Deployment for Project: $ProjectId" -ForegroundColor Green

# 1. Enable APIs
Write-Host "Enabling Google Cloud APIs..." -ForegroundColor Cyan
gcloud services enable run.googleapis.com sql-component.googleapis.com pubsub.googleapis.com containerregistry.googleapis.com
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to enable APIs"; exit 1 }

# 2. Configure Docker
Write-Host "Configuring Docker authentication..." -ForegroundColor Cyan
gcloud auth configure-docker
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to configure docker"; exit 1 }

# 3. Build and Push Images
$Services = @("api-gateway", "validation-service", "pricing-service", "quota-manager", "booking-orchestrator")

foreach ($svc in $Services) {
    Write-Host "Building $svc..." -ForegroundColor Cyan
    $ImageName = "gcr.io/$ProjectId/$svc`:latest"
    
    docker build -t $ImageName ".\services\$svc"
    if ($LASTEXITCODE -ne 0) { Write-Error "Build failed for $svc"; exit 1 }
    
    Write-Host "Pushing $svc..." -ForegroundColor Cyan
    docker push $ImageName
    if ($LASTEXITCODE -ne 0) { Write-Error "Push failed for $svc"; exit 1 }
}

# 4. Run Terraform
Write-Host "Applying Terraform configuration..." -ForegroundColor Cyan
Set-Location "infrastructure\terraform"

# Initialize if needed
if (-not (Test-Path ".terraform")) {
    terraform init
}

# Apply
terraform apply -var="project_id=$ProjectId" -auto-approve
if ($LASTEXITCODE -ne 0) { Write-Error "Terraform failed"; exit 1 }

# Get Output
$ApiUrl = terraform output -raw api_gateway_url
Set-Location "..\.."

Write-Host "`nDeployment Complete!" -ForegroundColor Green
Write-Host "API Gateway URL: $ApiUrl"
Write-Host "`nNEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Initialize the database manually using Cloud SQL Proxy or Cloud Console."
Write-Host "   Run the SQL scripts in .\database\schema.sql and .\database\functions.sql"
Write-Host "2. Configure your CLI:"
Write-Host "   `$env:API_URL = '$ApiUrl/api/v1'"
Write-Host "   python cli-client\main.py"
