"""
Idempotent Azure recovery/provisioning script for the Email Translation app.

Run from the project root (the folder containing main.py and requirements.txt):
    python fix_azure.py

This script is safe to rerun after an interrupted setup:
- It checks whether each Azure resource already exists before creating it.
- Existing resources are reused, not recreated.
- Existing .env entries are preserved; only Translator settings are updated.
- Existing .env is backed up before it is changed.
- Existing App Service settings are merged by Azure CLI.

Prerequisites:
    1. Azure CLI installed
    2. Run `az login`
    3. Select the intended subscription with `az account set --subscription ...`

IMPORTANT:
    App Service Basic B1 is paid. Foundry resource/model usage may also incur
    charges. Review the subscription and costs before proceeding.

This script provisions/configures resources. It does not deploy application code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration - keep these aligned with the original setup script.
# ---------------------------------------------------------------------------

RESOURCE_GROUP = "rg-tanishkalonkar-7649"
APP_LOCATION = "centralindia"

TRANSLATOR_NAME = "tanishkatranslator2026"
TRANSLATOR_LOCATION = "global"
TRANSLATOR_SKU = "F0"

FOUNDRY_RESOURCE_NAME = "translation-app-resource-tanishka2005"
FOUNDRY_PROJECT_NAME = "translation-app-tanishka2005"
FOUNDRY_LOCATION = "centralindia"
FOUNDRY_SKU = "S0"
FOUNDRY_RESOURCE_DOMAIN_NAME="translation-app-resource-tanishka695"

WEBAPP_NAME = "tanishka-email-translator-2026"
APP_SERVICE_PLAN = "asp-tanishka-email-translator-2026"
APP_SERVICE_SKU = "B1"
PYTHON_RUNTIME = "PYTHON:3.12"

STARTUP_COMMAND = (
    "python -m pip install -r /home/site/wwwroot/requirements.txt "
    "--target /home/site/wwwroot/.python_packages/lib/site-packages && "
    "PYTHONPATH=/home/site/wwwroot/.python_packages/lib/site-packages "
    "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
)

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
GITIGNORE_FILE = PROJECT_ROOT / ".gitignore"


def run_az(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Azure CLI reliably on Windows, Linux and macOS."""

    import os

    az_path = shutil.which("az") or shutil.which("az.cmd")

    # Check common Windows Azure CLI installation location.
    if not az_path and sys.platform == "win32":
        possible_paths = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Microsoft SDKs" / "Azure" / "CLI2" / "wbin" / "az.cmd",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs" / "Microsoft SDKs" / "Azure" / "CLI2" / "wbin" / "az.cmd",
        ]

        for candidate in possible_paths:
            if candidate.is_file():
                az_path = str(candidate)
                break

    if not az_path:
        raise RuntimeError(
            "Azure CLI was not found. Install it using:\n"
            "winget install --exact --id Microsoft.AzureCLI\n"
            "Then restart VS Code."
        )

    command = [az_path, *args]

    print("\n> " + " ".join(command[:5]) +
          (" ..." if len(command) > 5 else ""))

    result = subprocess.run(
        subprocess.list2cmdline(command) if sys.platform == "win32"
        else command,
        text=True,
        capture_output=True,
        shell=(sys.platform == "win32"),
        check=False
    )

    if check and result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout)

        if result.stderr.strip():
            print(result.stderr, file=sys.stderr)

        raise RuntimeError(
            f"Azure CLI failed with exit code {result.returncode}."
        )

    return result



def run_az_json(args: list[str], *, check: bool = True) -> Any:
    result = run_az(args + ["--output", "json"], check=check)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Azure CLI returned invalid JSON for: {' '.join(args)}") from exc


def resource_exists(show_args: list[str]) -> bool:
    """Return True only when Azure CLI successfully finds the resource."""
    result = run_az(show_args + ["--output", "none"], check=False)
    return result.returncode == 0


def ensure_azure_login() -> dict[str, Any]:
    account = run_az_json(["account", "show"])
    if not account:
        raise RuntimeError("Not signed in. Run `az login` and try again.")

    print(f"\nSigned in as: {account.get('user', {}).get('name', 'unknown user')}")
    print(f"Subscription: {account.get('name', 'unknown')}")
    print(f"Subscription ID: {account.get('id', 'unknown')}")

    if input("\nContinue with this subscription? Type YES: ").strip() != "YES":
        raise RuntimeError(
            "Stopped. Select the correct subscription using "
            "`az account set --subscription <subscription-id>`."
        )
    return account


def ensure_provider(namespace: str) -> None:
    print(f"\nChecking resource provider {namespace}...")
    run_az(["provider", "register", "--namespace", namespace])


def ensure_resource_group() -> None:
    print("\nChecking resource group...")
    if resource_exists(["group", "show", "--name", RESOURCE_GROUP]):
        print(f"Resource group {RESOURCE_GROUP} already exists; skipping creation.")
        return

    print(f"Creating resource group {RESOURCE_GROUP}...")
    run_az([
        "group", "create",
        "--name", RESOURCE_GROUP,
        "--location", APP_LOCATION,
    ])


def ensure_translator() -> dict[str, str]:
    print("\n=== Azure AI Translator ===")
    show_args = [
        "cognitiveservices", "account", "show",
        "--name", TRANSLATOR_NAME,
        "--resource-group", RESOURCE_GROUP,
    ]

    if resource_exists(show_args):
        print(f"Translator {TRANSLATOR_NAME} already exists; reusing it.")
    else:
        print(f"Creating Translator {TRANSLATOR_NAME}...")
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
    key = (keys or {}).get("key1")
    if not key:
        raise RuntimeError(
            "Translator exists, but Azure did not return key1. Check the resource's "
            "Keys and Endpoint page and your Azure permissions."
        )

    return {
        "TRANSLATOR_KEY": key,
        "TRANSLATOR_ENDPOINT": "https://api.cognitive.microsofttranslator.com",
        "TRANSLATOR_REGION": "global",
    }


def ensure_foundry_resource() -> None:
    print("\n=== Microsoft Foundry resource ===")
    show_args = [
        "cognitiveservices", "account", "show",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
    ]

    if resource_exists(show_args):
        print(f"Foundry resource {FOUNDRY_RESOURCE_NAME} already exists; reusing it.")
    else:
        print(f"Creating Foundry resource {FOUNDRY_RESOURCE_NAME}...")
        run_az([
            "cognitiveservices", "account", "create",
            "--name", FOUNDRY_RESOURCE_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--kind", "AIServices",
            "--sku", FOUNDRY_SKU,
            "--location", FOUNDRY_LOCATION,
            "--yes",
        ])

    # Set the custom domain only if it is not already configured.
    details = run_az_json(show_args) or {}
    current_domain = details.get("properties", {}).get("customSubDomainName")
    if current_domain == FOUNDRY_RESOURCE_NAME:
        print("Foundry custom subdomain is already configured; skipping.")
    else:
        print("Configuring Foundry custom subdomain...")
        run_az([
            "cognitiveservices", "account", "update",
            "--name", FOUNDRY_RESOURCE_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--custom-domain", FOUNDRY_RESOURCE_DOMAIN_NAME,
        ])


def ensure_foundry_project() -> None:
    print("\n=== Microsoft Foundry project ===")
    # `project show` is used as an existence check. A failed check triggers create.
    project_show = [
        "cognitiveservices", "account", "project", "show",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--project-name", FOUNDRY_PROJECT_NAME,
    ]

    if resource_exists(project_show):
        print(f"Foundry project {FOUNDRY_PROJECT_NAME} already exists; skipping creation.")
        return

    print(f"Creating Foundry project {FOUNDRY_PROJECT_NAME}...")
    run_az([
        "cognitiveservices", "account", "project", "create",
        "--name", FOUNDRY_RESOURCE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--project-name", FOUNDRY_PROJECT_NAME,
        "--location", FOUNDRY_LOCATION,
        "--display-name", FOUNDRY_PROJECT_NAME,
        "--description", "Email Translation Application AI Development Project",
    ])


def ensure_app_service_plan() -> None:
    print("\n=== Linux App Service plan ===")
    show_args = [
        "appservice", "plan", "show",
        "--name", APP_SERVICE_PLAN,
        "--resource-group", RESOURCE_GROUP,
    ]

    if resource_exists(show_args):
        print(f"App Service plan {APP_SERVICE_PLAN} already exists; skipping creation.")
        return

    print(f"Creating App Service plan {APP_SERVICE_PLAN} (paid {APP_SERVICE_SKU})...")
    run_az([
        "appservice", "plan", "create",
        "--name", APP_SERVICE_PLAN,
        "--resource-group", RESOURCE_GROUP,
        "--location", APP_LOCATION,
        "--sku", APP_SERVICE_SKU,
        "--is-linux",
    ])


def ensure_webapp() -> None:
    print("\n=== Web App ===")
    show_args = [
        "webapp", "show",
        "--name", WEBAPP_NAME,
        "--resource-group", RESOURCE_GROUP,
    ]

    if resource_exists(show_args):
        print(f"Web App {WEBAPP_NAME} already exists; skipping creation.")
    else:
        print(f"Creating Web App {WEBAPP_NAME}...")
        run_az([
            "webapp", "create",
            "--name", WEBAPP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--plan", APP_SERVICE_PLAN,
            "--runtime", PYTHON_RUNTIME,
        ])

    # Updating the startup command is an intentional configuration repair.
    run_az([
        "webapp", "config", "set",
        "--name", WEBAPP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--startup-file", STARTUP_COMMAND,
    ])


def update_local_env(values: dict[str, str]) -> None:
    """Update only specified keys, retaining all unrelated .env content."""
    old_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    keys = set(values)
    output: list[str] = []
    written: set[str] = set()

    for line in old_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in keys:
                if key not in written:
                    output.append(f"{key}={values[key]}")
                    written.add(key)
                continue
        output.append(line)

    for key, value in values.items():
        if key not in written:
            output.append(f"{key}={value}")

    if ENV_FILE.exists():
        backup = ENV_FILE.with_name(".env.backup")
        # Do not overwrite the first backup on subsequent reruns.
        if not backup.exists():
            shutil.copy2(ENV_FILE, backup)
            print(f"Backed up existing .env to {backup.name}.")
        else:
            print(f"Existing backup {backup.name} retained.")

    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    print("Updated local .env Translator settings; other entries were preserved.")


def ensure_env_is_ignored() -> None:
    lines = GITIGNORE_FILE.read_text(encoding="utf-8").splitlines() if GITIGNORE_FILE.exists() else []
    additions = [".env", ".env.*", "!.env.example"]
    missing = [entry for entry in additions if entry not in lines]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Local secrets")
        lines.extend(missing)
        GITIGNORE_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        print("Added .env ignore rules to .gitignore.")
    else:
        print(".env is already covered by .gitignore; no change needed.")


def configure_webapp(values: dict[str, str]) -> None:
    print("\n=== App Service settings ===")
    settings = [f"{key}={value}" for key, value in values.items()]
    settings.append("SCM_DO_BUILD_DURING_DEPLOYMENT=false")
    run_az([
        "webapp", "config", "appsettings", "set",
        "--name", WEBAPP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--settings",
        *settings,
    ])


def main() -> None:
    print("=" * 72)
    print("AZURE SETUP REPAIR - SAFE TO RERUN")
    print("=" * 72)
    print(f"Project folder: {PROJECT_ROOT}")
    print("Existing Azure resources will be reused, not recreated.")
    print("This script does not deploy your source code.")
    print("Cost warning: App Service B1 is paid; Foundry usage may also be billable.")

    if not (PROJECT_ROOT / "main.py").is_file():
        raise RuntimeError("main.py was not found beside fix_azure.py. Run from your project root.")
    if not (PROJECT_ROOT / "requirements.txt").is_file():
        raise RuntimeError("requirements.txt was not found beside fix_azure.py. Run from your project root.")

    if input("\nThis may create billable Azure resources. Type REPAIR to continue: ").strip() != "REPAIR":
        print("Cancelled. No Azure changes were requested.")
        return

    ensure_azure_login()
    ensure_provider("Microsoft.CognitiveServices")
    ensure_provider("Microsoft.Web")
    ensure_resource_group()

    translator_values = ensure_translator()
    ensure_foundry_resource()
    ensure_foundry_project()
    ensure_app_service_plan()
    ensure_webapp()

    update_local_env(translator_values)
    ensure_env_is_ignored()
    configure_webapp(translator_values)

    print("\n" + "=" * 72)
    print("AZURE REPAIR / SETUP CHECK FINISHED")
    print("=" * 72)
    print(f"Resource group:   {RESOURCE_GROUP}")
    print(f"Translator:       {TRANSLATOR_NAME} (F0 / Global)")
    print(f"Foundry resource: {FOUNDRY_RESOURCE_NAME}")
    print(f"Foundry project:  {FOUNDRY_PROJECT_NAME}")
    print(f"App Service plan: {APP_SERVICE_PLAN} ({APP_SERVICE_SKU} / Linux)")
    print(f"Web App:          {WEBAPP_NAME}")
    print(f"Web App URL:      https://{WEBAPP_NAME}.azurewebsites.net")
    print(f"Local .env:       {ENV_FILE}")
    print("\nNext: deploy the project using the VS Code Azure App Service extension.")
    print("Never commit or share .env or the Translator key.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. You can safely rerun this script; existing resources are checked.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nREPAIR FAILED: {exc}", file=sys.stderr)
        print("Fix the reported issue, then rerun fix_azure.py. Existing resources are checked.")
        sys.exit(1)
