# Daily Loop

Waymark is designed to be useful when you come back tomorrow, not only when you
remember a command. The daily loop starts with:

```bash
waymark today
```

This is an app-only summary. It reads your local database and shows:

- captures from today
- reflection windows that have memories but no saved reflection yet
- decisions due for review or waiting for an outcome
- copyable next commands

In the guided interface (`waymark`), open **Today** from the main menu or press
`y`. The screen can jump directly to daily capture, the next due reflection, or
decision review.

## Start with one capture

If nothing is captured today, Waymark suggests a plain daily capture:

```bash
waymark capture --type daily "One detail from today that future-me should remember."
```

Keep this small. A daily memory can be an ordinary detail, a conversation, a
constraint, or a feeling you may want later.

## Reflect when a window is due

When today, week, or month has memories that have not been saved into a
reflection yet, `waymark today` shows the matching command:

```bash
waymark reflect --period today --save
waymark reflect --period week --save
```

Reflections are source-grounded summaries of saved memories. Saving one gives
future comparisons and trends something concrete to use.

## Review decisions

If a decision has a review date due today or earlier, or if a decided item still
needs an outcome, the daily loop points you at:

```bash
waymark decision review
```

That keeps decisions from becoming static notes. A decision can move from open,
to decided, to reviewed with an outcome.
