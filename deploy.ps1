
# ==========================================
# Azure Email Translator - Deployment Script
# ==========================================

$ErrorActionPreference = "Stop"

# Azure configuration
$RESOURCE_GROUP = "rg-tanishkalonkar-7649"
$APP_NAME = "tanishka-email-translator-2026"

$PROJECT_DIR = $PSScriptRoot
$ZIP_FILE = Join-Path $PROJECT_DIR "deploy.zip"
$STAGING_DIR = Join-Path $PROJECT_DIR "deploy_temp"

$APP_URL = "https://$APP_NAME.azurewebsites.net"

Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host " Azure Email Translator Deployment"
Write-Host "==================================" -ForegroundColor Cyan

# 1. Check Azure CLI
Write-Host "`n[1/7] Checking Azure CLI..."

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is not installed. Install it from https://aka.ms/installazurecliwindows"
}

# 2. Check Azure login
Write-Host "`n[2/7] Checking Azure login..."

az account show --output none

if ($LASTEXITCODE -ne 0) {
    az login
    if ($LASTEXITCODE -ne 0) {
        throw "Azure login failed."
    }
}

# 3. Check project files
Write-Host "`n[3/7] Checking project files..."

if (-not (Test-Path (Join-Path $PROJECT_DIR "main.py"))) {
    throw "main.py not found."
}

if (-not (Test-Path (Join-Path $PROJECT_DIR "requirements.txt"))) {
    throw "requirements.txt not found."
}

if (-not (Test-Path (Join-Path $PROJECT_DIR "frontend"))) {
    throw "frontend folder not found."
}

# 4. Read Azure Translator settings from .env
Write-Host "`n[4/7] Reading Azure settings from .env..."

$ENV_FILE = Join-Path $PROJECT_DIR ".env"

if (-not (Test-Path $ENV_FILE)) {
    throw ".env file not found in project directory."
}

$ENV_VALUES = @{}

Get-Content $ENV_FILE | ForEach-Object {
    $line = $_.Trim()

    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line -split "=", 2
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()

        # Remove optional surrounding quotes
        $value = $value.Trim('"').Trim("'")

        $ENV_VALUES[$name] = $value
    }
}

$TRANSLATOR_KEY = $ENV_VALUES["TRANSLATOR_KEY"]
$TRANSLATOR_ENDPOINT = $ENV_VALUES["TRANSLATOR_ENDPOINT"]
$TRANSLATOR_REGION = $ENV_VALUES["TRANSLATOR_REGION"]


if ([string]::IsNullOrWhiteSpace($TRANSLATOR_KEY)) {
    throw "TRANSLATOR_KEY is missing from .env"
}


if ([string]::IsNullOrWhiteSpace($TRANSLATOR_ENDPOINT)) {
    $TRANSLATOR_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
}

if ([string]::IsNullOrWhiteSpace($TRANSLATOR_REGION)) {
    $TRANSLATOR_REGION = "global"
}

Write-Host "Azure settings loaded successfully."

# Configure Azure App Service settings
az webapp config appsettings set `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --settings `
    "SCM_DO_BUILD_DURING_DEPLOYMENT=true" `
    "TRANSLATOR_KEY=$TRANSLATOR_KEY" `
    "TRANSLATOR_ENDPOINT=$TRANSLATOR_ENDPOINT" `
    "TRANSLATOR_REGION=$TRANSLATOR_REGION" `
    --output none

if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure Azure application settings."
}

# Clear the key from this script's variables
$TRANSLATOR_KEY = $null
$ENV_VALUES["TRANSLATOR_KEY"] = $null


# 5. Configure FastAPI startup
Write-Host "`n[5/7] Configuring FastAPI startup..."

az webapp config set `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000" `
    --output none

if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure startup command."
}

# 6. Prepare deployment ZIP
Write-Host "`n[6/7] Preparing deployment package..."

if (Test-Path $STAGING_DIR) {
    Remove-Item $STAGING_DIR -Recurse -Force
}

New-Item -ItemType Directory -Path $STAGING_DIR | Out-Null

Copy-Item (Join-Path $PROJECT_DIR "main.py") $STAGING_DIR
Copy-Item (Join-Path $PROJECT_DIR "requirements.txt") $STAGING_DIR
Copy-Item (Join-Path $PROJECT_DIR "frontend") $STAGING_DIR -Recurse

if (Test-Path $ZIP_FILE) {
    Remove-Item $ZIP_FILE -Force
}

Compress-Archive `
    -Path "$STAGING_DIR\*" `
    -DestinationPath $ZIP_FILE `
    -Force

# 7. Deploy
Write-Host "`n[7/7] Deploying to Azure..."

az webapp deploy `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME `
    --src-path $ZIP_FILE `
    --type zip

if ($LASTEXITCODE -ne 0) {
    throw "Azure deployment failed."
}

Write-Host "`nRestarting Azure Web App..." -ForegroundColor Yellow

az webapp restart `
    --resource-group $RESOURCE_GROUP `
    --name $APP_NAME

if ($LASTEXITCODE -ne 0) {
    throw "Azure restart failed."
}

Write-Host "`n==================================" -ForegroundColor Green
Write-Host " DEPLOYMENT COMPLETED!"
Write-Host "==================================" -ForegroundColor Green

Write-Host "`nYour application URL:"
Write-Host $APP_URL -ForegroundColor Cyan

Write-Host "`nAPI documentation:"
Write-Host "$APP_URL/docs" -ForegroundColor Cyan

Write-Host "`nHealth check:"
Write-Host "$APP_URL/health" -ForegroundColor Cyan

Write-Host "`nDeployment ZIP: $ZIP_FILE"
