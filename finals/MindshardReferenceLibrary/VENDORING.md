# Vendoring

This folder is designed to be copied or zipped as a single unit.

## Portability Rules

- Keep the whole folder together
- Do not replace packaged imports with parent-repo imports
- Keep settings relative
- Avoid machine-specific source paths in code
- Keep the local `src/core/reference_library/` tree as the owned runtime core
- Generated exports belong in the global library root, not in the package folder

## Optional Runtime

- The tree-sitter provider is optional
- If its runtime is unavailable, the package still works through prose and fallback chunking

## Before Shipping

1. Run `python smoke_test.py`
2. Run `python -m unittest discover -s tests -v`
3. Run `python app.py --health`
4. Remove `__pycache__` folders if you do not want them in the archive
5. Zip the folder root, not individual files

## After Unzipping Elsewhere

1. Install Python requirements if needed:

```powershell
pip install -r requirements.txt
```

2. Run the smoke test:

```powershell
python smoke_test.py
```

3. Run the regression suite:

```powershell
python -m unittest discover -s tests -v
```

4. Start the MCP server:

```powershell
python mcp_server.py
```
