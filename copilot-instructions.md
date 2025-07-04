# Copilot Instructions

# Purpose

This file provides workspace-specific instructions for GitHub Copilot and Copilot Chat to ensure consistent, context-aware code suggestions and automation for the kitchen-epaper-renderer project.

# Guidelines

- Always use relative paths for local development (e.g., `icons/png` for icons).
- When referencing icons in code, only use PNG files that are guaranteed to exist in the `icons/png` directory.
- For weather icon mapping, default to `cloudy.png` if unsure or if a specific icon is missing.
- Environment variables required for local and cloud runs:
  - `CALENDAR_ID`
  - `YR_LAT`
  - `YR_LON`
  - `SECRET_NAME`
- Use the VS Code task "Run epaper locally with env vars" for local development.
- Do not modify `.vscode/settings.json` or `.vscode/tasks.json` to be ignored by Copilot or Git.
- When adding new icons or fonts, update `.gitignore` to avoid committing binaries.
- Always check for file existence before referencing in code if unsure.
- You should always do the changes yourself instead of suggesting the user to do them.
- You should always run commands yourself and only ask for user confirmation if needed.
- When running the application locally, always use the "Run epaper locally with env vars" task and check the terminal for errors automatically.

# Usage

- This file should be named `copilot-instructions.md` and placed in the project root.
- Copilot and Copilot Chat should always consider these instructions for all code completions and automation in this workspace.

# Copilot Usage Instructions

When you ask Copilot to commit and push changes, it should always run a single shell command of the form:

```
git add . && git commit -m "<meaningful commit message>" && git push
```

The commit message should be adapted to describe the change, e.g.:

```
git add . && git commit -m "Update README: clarify Secret Manager permissions for Cloud Function and service accounts" && git push
```

This ensures all changes are staged, committed, and pushed in one atomic operation.
