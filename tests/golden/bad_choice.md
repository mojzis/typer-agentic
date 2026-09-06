✗ Usage error in `myapp sync`: Invalid value for '--env': 'prd' is not one of 'dev', 'prod'.

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command.

Did you mean: prod

Fix and retry (one change): Use one of: dev, prod. Run the corrected example.

```
myapp sync ./PATH --env prod
```

Valid options:
  --verbose, -v  flag              Enable verbose output.
  --count        INTEGER           How many.
  --env          CHOICE[dev|prod]  Target environment.

Required arguments: PATH

Full reference: myapp sync --help
