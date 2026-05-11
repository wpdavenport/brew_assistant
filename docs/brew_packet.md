# Brew Packet Workflow

This is the simple path for brewers who just want a printable brew-day packet.

## Run It

```bash
make brew-packet RECIPE=recipes/lodestar_double_ipa_22A.md
```

With a brew date:

```bash
make brew-packet RECIPE=recipes/lodestar_double_ipa_22A.md DATE=2026-06-15
```

## What It Creates

- A compact recipe print in `recipes/html_exports/`
- A full operational brew-day sheet in `brewing/brew_day_sheets/`
- A dated brew-day sheet in `brewing/brew_day_sheets/archive/` when `DATE` is provided

## What Good Looks Like

The command ends with:

```text
BREW_PACKET_READY
```

That means the printable recipe and brew-day sheet passed the targeted checks.

## When Something Is Missing

The command ends with:

```text
BREW_PACKET_NEEDS_ATTENTION
```

The files may still be created, but the brewer needs to fix the listed issue before brew day.
Generated brew-day sheets keep missing sections visible as `ACTION REQUIRED` rows instead of leaving them out.

That behavior matters because a recipe is not an execution plan. The brew-day sheet must still cover water prep, yeast source, mash execution, boil additions, fermentation, packaging, and notes even when the imported recipe is incomplete.

## No-Terminal Recipe Inbox

For a brewer-facing setup, use the recipe inbox watcher.

Once the watcher is running, the workflow is:

1. Drop a recipe file into `recipe_inbox/`.
2. Wait for the packet report to appear under `brew_packets/`.
3. Open `brew_packets/<recipe-name>/index.html`.

Supported dropped files:
- `.md`
- `.markdown`
- `.txt` with markdown-style recipe sections

Optional date line inside the recipe file:

```text
Brew Date: 2026-06-15
```

Manual watcher:

```bash
make brew-inbox-watch
```

macOS background watcher:

```bash
make brew-inbox-service-install
```

Status and uninstall:

```bash
make brew-inbox-service-status
make brew-inbox-service-uninstall
```
