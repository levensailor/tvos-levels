# Contributing

Thanks for helping improve Band Levels. Every change goes through a feature branch and a pull request.

## 1. Create a feature branch

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description
```

Use `fix/` for bug fixes and `docs/` for documentation-only changes.

## 2. Make and check your change

```bash
uv sync
uv run ruff check .
uv run pytest
```

For tvOS changes, run Product → Test in Xcode against an Apple TV simulator. Keep the bridge contract in `level_bridge/models.py` and `BandLevels/BandLevels/Models/BridgeContract.swift` in sync, and update [docs/BRIDGE_PROTOCOL.md](docs/BRIDGE_PROTOCOL.md) when either changes.

New features get a timestamped entry in [CHANGELOG.md](CHANGELOG.md) that reuses the commit message.

## 3. Open a pull request

```bash
git push -u origin feature/short-description
gh pr create --title "Short summary" --body "Why this change should be added, what it changes, and how you tested it."
```

The pull request description must explain **why the change should be added to the repository**: the problem it solves or the value it adds for people running the dashboard. Include how you tested it (unit tests, simulator, real Logic Pro session). CI must pass before merge.

Never commit `.env`, `config/tracks.json`, `DeveloperSettings.xcconfig`, or the Satoshi font file.
