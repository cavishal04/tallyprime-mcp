# Scripts

- **check.sh** — runs the same lint/test/build checks as CI, locally.
  ```bash
  ./scripts/check.sh
  ```

Windows users: run the equivalent commands directly (`ruff check src tests`,
`pytest`, `python -m build`) rather than this shell script, or run it under
WSL/Git Bash.
