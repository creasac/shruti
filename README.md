# shruti

Minimal desktop speech-to-text using Gemini.

## One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/creasac/shruti/main/bootstrap.sh | bash
```

What setup asks during install:

- Gemini API key (hidden input)
- Preferred hotkey (default `Ctrl+Space`)
- Whether to autostart the daemon at login

During hotkey setup, you are asked to press the chosen key combo once.
If it is not detected, it likely conflicts with another global shortcut.

## Alternate install

```bash
git clone https://github.com/creasac/shruti.git
cd shruti
./install.sh
```

## Runtime behavior

- Hotkey press: start recording
- Hotkey press again: stop recording and transcribe
- `Esc`: cancel current recording
- Recording auto-stops after `max_record_seconds` (default: `300`)

## Configuration

Files:

- `~/.config/shruti/config.toml`
- `~/.config/shruti/credentials.toml`

Editable config fields:

- `model`
- `hotkey`
- `max_record_seconds`
- `sample_rate`
- `channels`
- `prompt`

## Commands

```bash
shruti setup
shruti doctor --verbose
shruti daemon
shruti transcribe
```

## Limitations

- Linux X11 only

## License

MIT. See [LICENSE](LICENSE).
