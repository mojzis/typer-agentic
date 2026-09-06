✗ Usage error in `myapp sync`: Option '--count' requires an argument.

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command.

Fix and retry (one change): Fix how '--count' is used, then retry. Run the corrected example.

```
myapp sync ./PATH --count 1
```

Valid options:
  --verbose, -v  flag              Enable verbose output.
  --count        INTEGER           How many.
  --env          CHOICE[dev|prod]  Target environment.

Required arguments: PATH

Full reference: myapp sync --help
