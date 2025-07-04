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
