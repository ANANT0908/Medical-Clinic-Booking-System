Write-Host "Installing dependencies..." -ForegroundColor Cyan

$reqs = @(
    "services/api-gateway/requirements.txt",
    "services/validation-service/requirements.txt",
    "services/pricing-service/requirements.txt",
    "services/quota-manager/requirements.txt",
    "services/booking-orchestrator/requirements.txt",
    "cli-client/requirements.txt"
)

foreach ($file in $reqs) {
    Write-Host "Installing from $file..."
    py -m pip install -r $file
}

Write-Host "Done!" -ForegroundColor Green
