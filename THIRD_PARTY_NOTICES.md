# Third-party notices

| Component | How Band Levels uses it | License |
| --- | --- | --- |
| [Inter](https://github.com/rsms/inter) 4.1 | Bundled in the app (`InterVariable.ttf`) as the fallback typeface | SIL Open Font License 1.1, included at `BandLevels/BandLevels/Resources/Fonts/Inter-OFL-LICENSE.txt` and shipped inside the app |
| [Satoshi](https://www.fontshare.com/fonts/satoshi) | Downloaded at build time by `scripts/fetch-fonts.sh` and embedded in your own app build; not stored in this repository | ITF Free Font License 2.0 (embedding in apps permitted; redistribution of the font files is not) |
| [Logic Pro MCP](https://github.com/MongLong0214/logic-pro-mcp) v3.18.0 | Installed separately; the bridge launches it over MCP stdio to read `logic://tracks` | MIT |
| [BlackHole](https://github.com/ExistentialAudio/BlackHole) | Installed separately as a macOS audio driver; not linked or redistributed | GPL-3.0 |
| Python packages (FastAPI, Uvicorn, Pydantic, python-dotenv, NumPy, SciPy, sounddevice, MCP SDK, tzdata) | Bridge runtime dependencies installed by `uv` | Their respective licenses (MIT, BSD, Apache-2.0) |

Logic Pro is a trademark of Apple Inc. SSL and SSL 360 are trademarks of Solid State Logic. This project is not affiliated with either company.
