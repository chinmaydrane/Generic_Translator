from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path.cwd()
zip_path = root / "deploy.zip"

with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
    z.write(root / "main.py", "main.py")
    z.write(root / "requirements.txt", "requirements.txt")

    for file in (root / "frontend").rglob("*"):
        if file.is_file():
            archive_name = file.relative_to(root).as_posix()
            z.write(file, archive_name)

print("Created:", zip_path)
