---
name: "myapp"
description: "Demo tool for tests."
---

# myapp

## When to use

Demo tool for tests.

## Commands

### myapp sync

Sync a path.

Arguments:
  PATH  PATH  required  Where to sync.

Options:
  --verbose, -v  flag              Enable verbose output.
  --count        INTEGER           How many.
  --env          CHOICE[dev|prod]  Target environment.

Example:

```
myapp sync ./PATH
```

### myapp push

Push to a target.

Arguments:
  TARGET  TEXT  required

Options:
  --tags     TEXT           Tags.
  --retries  INTEGER[0..5]  Retry budget.

Example:

```
myapp push VALUE
```

### myapp fail

Exit with a code, or abort.

Options:
  --code  INTEGER

Example:

```
myapp fail
```

### myapp returns-int

Return an int (stock Typer still exits 0).

Example:

```
myapp returns-int
```

### myapp interrupt

Simulate Ctrl-C.

Example:

```
myapp interrupt
```

### myapp boom

Raise a runtime error.

Example:

```
myapp boom
```

## On usage errors

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command. The error block always contains exactly one corrected example; run it.
