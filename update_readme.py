#!/bin/env python3

from pathlib import Path

readme_path = Path('README.md')
init_path = Path('src/benlink/__init__.py')

readme_content = readme_path.read_text().splitlines()

init_content = init_path.read_text().splitlines()

docstring_start = init_content.index('"""')

if docstring_start == -1:
    raise ValueError("No docstring found in __init__.py.")

docstring_end = init_content.index('"""', docstring_start + 1)

if docstring_end == -1:
    raise ValueError("No end of docstring found in __init__.py.")

readme_start = readme_content.index('## Overview')

if readme_start == -1:
    raise ValueError("No Overview section found in README.md.")


updated_content = [
    *init_content[:docstring_start + 1],
    *readme_content[readme_start:],
    *init_content[docstring_end:]
]

init_path.write_text("\n".join(updated_content))

print(f"README content has been updated into module definition")
