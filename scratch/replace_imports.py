import glob
import os

files = glob.glob("apps/*/tests/*.py")
for f in files:
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()

    new_content = content.replace("apps.master_data.tests.factories", "apps.inventory.tests.factories")
    new_content = new_content.replace("apps.accounts.tests.factories", "apps.inventory.tests.factories")

    if new_content != content:
        with open(f, "w", encoding="utf-8") as file:
            file.write(new_content)
        print(f"Updated {f}")
