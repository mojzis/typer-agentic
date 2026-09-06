✗ Usage error in `myapp sync`: No such option: --verbos

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command.

Did you mean: --verbose

Fix and retry (one change): Replace '--verbos' with '--verbose'. Run the corrected example.

```
myapp sync ./PATH --verbose
```

Valid options:
  --verbose, -v  flag              Enable verbose output.
  --count        INTEGER           How many.
  --env          CHOICE[dev|prod]  Target environment.

Required arguments: PATH

Full reference: myapp sync --help
