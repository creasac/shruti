# shruti

Minimal desktop speech-to-text using Gemini.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/creasac/shruti/main/bootstrap.sh | bash
```

What setup asks:

- Gemini API key (hidden input)
- Preferred hotkey (default `Ctrl+Space`)

Hotkey behavior after setup:

- Press hotkey once: start recording
- Press hotkey again: stop and transcribe
- Press `Esc`: cancel current recording

No background daemon runs while idle.

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
shruti oneshot
```

## Limitations

- Linux X11 only (Wayland blocks unrestricted global hotkey/input injection for security)

## License

MIT. See [LICENSE](LICENSE).
