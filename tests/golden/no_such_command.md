✗ Usage error in `myapp`: No such command 'synk'.

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command.

Did you mean: sync

Fix and retry (one change): Use the subcommand 'sync'. Run the corrected example.

```
myapp sync
```

Valid subcommands:
  sync         Sync a path.
  push         Push to a target.
  fail         Exit with a code, or abort.
  returns-int  Return an int (stock Typer still exits 0).
  interrupt    Simulate Ctrl-C.
  boom         Raise a runtime error.

Full reference: myapp --help
