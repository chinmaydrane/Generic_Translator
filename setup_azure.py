"""
Azure provisioning script for the Azure Email Translation Web Application.

Based on the supplied project documentation:
- Resource group: rg-tanishkalonkar-7649
- Region for App Service / Foundry: Central India
- Translator: TextTranslation, Free F0, Global
- App Service: Linux, Python 3.12, Basic B1
- Foundry resource/project: translation-app-resource / translation-app

Run this script from the project root (the folder containing main.py).
Prerequisite: Azure CLI installed and authenticated with `az login`.

IMPORTANT:
- Basic B1 App Service is PAID and can consume your Azure credits.
- Foundry resource/model usage may also be billable.
- This script creates resources; it does NOT deploy your source code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


# ---------------------------------------------------------------------------
# PROJECT CONFIGURATION
# Edit these values if you want different names or already have resources.
# Azure resource names such as Web App names must be globally unique.
# ---------------------------------------------------------------------------

RESOURCE_GROUP = "rg-tanishkalonkar-7649"
APP_LOCATION = "centralindia"

TRANSLATOR_NAME = "tanishkatranslator2026"
TRANSLATOR_LOCATION = "global"       # Translator Global endpoint
TRANSLATOR_SKU = "F0"                 # Free tier

FOUNDRY_RESOURCE_NAME = "translation-app-resource-tanishka"
FOUNDRY_PROJECT_NAME = "translation-app-tanishka"
FOUNDRY_LOCATION = "centralindia"
FOUNDRY_SKU = "S0"                    # Resource tier; model usage can incur charges

WEBAPP_NAME = "tanishka-email-translator-2026"
APP_SERVICE_PLAN = "asp-tanishka-email-translator-2026"
APP_SERVICE_SKU = "B1"                # PAID tier, as specified in the document
PYTHON_RUNTIME = "PYTHON:3.12"

# The supplied documentation uses this startup command.
STARTUP_COMMAND = (
    "python -m pip install -r /home/site/wwwroot/requirements.txt "
    "--target /home/site/wwwroot/.python_packages/lib/site-packages && "
    "PYTHONPATH=/home/site/wwwroot/.python_packages/lib/site-packages "
    "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
)

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
GITIGNORE_FILE = PROJECT_ROOT / ".gitignore"


def run_az(args: list[str], *, json_output: bool = False):
    """Run Azure CLI and return stdout."""

    command = ["az", *args]

    if json_output and "--output" not in args and "-o" not in args:
        command += ["--output", "json"]

    print("\n> " + " ".join(command[:5]) +
          (" ..." if len(command) > 5 else ""))

    try:
        if sys.platform == "win32":
            # Windows: Execute Azure CLI through cmd.exe
            command_text = subprocess.list2cmdline(command)

            result = subprocess.run(
                command_text,
                text=True,
                capture_output=True,
                shell=True,
                check=False
            )

        else:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                shell=False,
                check=False
            )

    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI not found. Install Azure CLI and restart VS Code."
        )

    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout)

        if result.stderr.strip():
            print(result.stderr, file=sys.stderr)

        raise RuntimeError(
            f"Azure CLI command failed with exit code {result.returncode}."
        )

    return result.stdout.strip()

def run_az_json(args: list[str]):
    output = run_az(args, json_output=True)
    return json.loads(output) if output else {}


def ensure_azure_cli():
    if shutil.which("az") is None:
        raise RuntimeError(
            "Azure CLI was not found. Install it from "
            "https://learn.microsoft.com/cli/azure/install-azure-cli "
            "and reopen the terminal."
        )

    try:
        account = run_az_json(["account", "show"])
    except RuntimeError as exc:
        raise RuntimeError(
            "You are not signed in to Azure CLI. Run `az login`, then rerun "
            "this script."
        ) from exc

    print(f"\nSigned in as: {account.get('user', {}).get('name', 'unknown user')}")
    print(f"Active subscription: {account.get('name', 'unknown')}")
    print(f"Subscription ID: {account.get('id', 'unknown')}")

    answer = input(
        "\nUse this subscription? Type YES to continue: "
    ).strip()
    if answer != "YES":
        raise RuntimeError(
            "Stopped. Select the intended subscription with "
            "`az account set --subscription <subscription-id>` and rerun."
        )

    return account


def ensure_provider(namespace: str):
    run_az(["provider", "register", "--namespace", namespace])


def ensure_resource_group():
    run_az([
        "group", "create",
        "--name", RESOURCE_GROUP,
        "--location", APP_LOCATION,
    ])


def create_translator():
    print("\n=== Creating/checking Azure AI Translator (Free F0) ===")
    run_az([
        "cognitiveservices", "account", "create",
        "--name", TRANSLATOR_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--kind", "TextTranslation",
        "--sku", TRANSLATOR_SKU,
        "--location", TRANSLATOR_LOCATION,
        "--yes",
    ])

    keys = run_az_json([
        "cognitiveservices", "account", "keys", "list",
        "--name", TRANSLATOR_NAME,
        "--resource-group", RESOURCE_GROUP,
    ])
    key = keys.get("key1")
    if not key:
        raise RuntimeError(
            "Translator was created, but Azure CLI did not return key1. "
            "Open the Translator resource in Azure Portal and check Keys and Endpoint."
        )

    return {
        "TRANSLATOR_KEY": key,
        "TRANSLATOR_ENDPOINT": "https://api.cognitive.microsofttranslator.com",
        "TRANSLATOR_REGION": "global",
    }


def create_foundry_resource_and_project(subscription_id: str):
    print("\n=== Creating/checking Microsoft Foundry resource ===")

    # Step 1: Create or check the Foundry resource
    run_az([
        "cognitiveservices", "account", "create",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--kind", "AIServices",
        "--sku", FOUNDRY_SKU,
        "--location", FOUNDRY_LOCATION,
        "--yes",
    ])

    # Step 2: Configure the required custom subdomain
    print("\n=== Configuring Foundry custom subdomain ===")

    run_az([
        "cognitiveservices", "account", "update",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--custom-domain", FOUNDRY_RESOURCE_NAME,
    ])

    # Step 3: Create the Foundry project
    print("\n=== Creating Foundry project ===")

    run_az([
        "cognitiveservices", "account", "project", "create",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--project-name", FOUNDRY_PROJECT_NAME,
        "--location", FOUNDRY_LOCATION,
        "--display-name", FOUNDRY_PROJECT_NAME,
        "--description",
        "Email Translation Application AI Development Project",
    ])

    print("\nFoundry resource and project configured successfully!")

def create_app_service():
    print("\n=== Creating/checking Linux App Service (Basic B1 - paid) ===")
    run_az([
        "appservice", "plan", "create",
        "--name", APP_SERVICE_PLAN,
        "--resource-group", RESOURCE_GROUP,
        "--location", APP_LOCATION,
        "--sku", APP_SERVICE_SKU,
        "--is-linux",
    ])

    # If the web app already exists, leave it in place; otherwise create it.
    existing = subprocess.run(
        [
            "az", "webapp", "show",
            "--name", WEBAPP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--output", "none",
        ],
        text=True,
        capture_output=True,
        shell=False,
    )
    if existing.returncode != 0:
        run_az([
            "webapp", "create",
            "--name", WEBAPP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--plan", APP_SERVICE_PLAN,
            "--runtime", PYTHON_RUNTIME,
        ])
    else:
        print(f"Web App {WEBAPP_NAME} already exists; not recreating it.")

    run_az([
        "webapp", "config", "set",
        "--name", WEBAPP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--startup-file", STARTUP_COMMAND,
    ])


def write_env_file(values: dict[str, str]):
    """Safely update only the Translator variables, preserving other .env entries."""
    existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    keys_to_update = set(values)
    output_lines = []
    seen = set()

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in keys_to_update:
                if key not in seen:
                    output_lines.append(f"{key}={values[key]}")
                    seen.add(key)
                continue
        output_lines.append(line)

    for key, value in values.items():
        if key not in seen:
            output_lines.append(f"{key}={value}")

    if ENV_FILE.exists():
        backup = ENV_FILE.with_name(".env.backup")
        shutil.copy2(ENV_FILE, backup)
        print(f"Existing .env backed up to: {backup.name}")

    ENV_FILE.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Local Translator settings written to: {ENV_FILE}")


def ensure_env_is_ignored():
    lines = GITIGNORE_FILE.read_text(encoding="utf-8").splitlines() if GITIGNORE_FILE.exists() else []
    if ".env" not in lines:
        lines += ["", "# Local secrets", ".env", ".env.*", "!.env.example"]
        GITIGNORE_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        print("Added .env entries to .gitignore.")


def configure_webapp(translator_values: dict[str, str]):
    print("\n=== Configuring App Service environment variables ===")
    settings = [
        f"{key}={value}" for key, value in translator_values.items()
    ]
    settings += [
        "SCM_DO_BUILD_DURING_DEPLOYMENT=false",
    ]
    run_az([
        "webapp", "config", "appsettings", "set",
        "--name", WEBAPP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--settings",
        *settings,
    ])


def main():
    print("=" * 72)
    print("AZURE SETUP - EMAIL TRANSLATION WEB APPLICATION")
    print("=" * 72)
    print(f"Project folder: {PROJECT_ROOT}")
    print("\nThis script provisions Azure resources; it does not deploy your code.")
    print("The App Service plan is Basic B1 (paid). Foundry usage may also cost money.")
    print("The Translator resource is configured for Free F0.")

    if not (PROJECT_ROOT / "main.py").exists():
        raise RuntimeError(
            "main.py was not found beside setup_azure.py. "
            "Move this script to the project root (same folder as main.py)."
        )

    if not (PROJECT_ROOT / "requirements.txt").exists():
        raise RuntimeError(
            "requirements.txt was not found beside setup_azure.py. "
            "Move this script to the project root (same folder as requirements.txt)."
        )

    answer = input(
        "\nThis will create/check Azure resources and may consume credits. "
        "Type CREATE to proceed: "
    ).strip()
    if answer != "CREATE":
        print("Cancelled. No resources were created.")
        return

    account = ensure_azure_cli()
    ensure_provider("Microsoft.CognitiveServices")
    ensure_provider("Microsoft.Web")
    ensure_resource_group()

    translator_values = create_translator()
    create_foundry_resource_and_project(account["id"])
    create_app_service()
    write_env_file(translator_values)
    ensure_env_is_ignored()
    configure_webapp(translator_values)

    print("\n" + "=" * 72)
    print("AZURE RESOURCE SETUP FINISHED")
    print("=" * 72)
    print(f"Resource group:       {RESOURCE_GROUP}")
    print(f"Translator:           {TRANSLATOR_NAME} (F0 / Global)")
    print(f"Foundry resource:     {FOUNDRY_RESOURCE_NAME}")
    print(f"Foundry project:      {FOUNDRY_PROJECT_NAME}")
    print(f"App Service plan:     {APP_SERVICE_PLAN} (B1 / Linux)")
    print(f"Web App:              {WEBAPP_NAME}")
    print(f"Web App URL:          https://{WEBAPP_NAME}.azurewebsites.net")
    print(f"Local configuration:  {ENV_FILE}")
    print("\nNext: deploy the project folder using the VS Code Azure App Service")
    print("extension. Do not commit or share the .env file or Translator key.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as error:
        print(f"\nSETUP FAILED: {error}", file=sys.stderr)
        sys.exit(1)
