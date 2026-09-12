# shruti

Minimal desktop speech-to-text using Gemini.

<img width="1254" height="1254" alt="shruti-logo" src="https://github.com/user-attachments/assets/6a7ab1ae-366e-4d8e-a6a3-7681d2344f10" />

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/creasac/shruti/master/bootstrap.sh | bash
```

Run this as your normal user from an X11 desktop terminal. You need Python 3.11+
and `curl`. The installer installs system dependencies using `sudo` with
apt, dnf, or pacman, then installs Shruti into a private virtual environment.

No Git installation or clone is needed. The source archive is downloaded to a
temporary directory and removed when the installer exits, including on failure.
The installed package is independent of that source:

- `~/.local/share/shruti/venv/` — Python runtime and installed package
- `~/.local/bin/shruti` — command
- `~/.local/bin/shruti-uninstall` — uninstaller
- `~/.config/shruti/` — preferences and credentials

If `~/.local/bin` is not on your PATH, add this to your shell configuration and
open a new terminal (or use the full command path printed by the installer):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

To install without prompts, after installing the system dependencies yourself:

```bash
curl -fsSL https://raw.githubusercontent.com/creasac/shruti/master/bootstrap.sh | bash -s -- --skip-system-packages --no-setup
~/.local/bin/shruti setup
```

On Ubuntu/Debian those dependencies are `xdotool`, `portaudio19-dev`,
`python3-tk`, and `python3-venv`. Without a terminal, setup is deferred and the
installer prints the command to run later. Setup reads from the terminal even
when installation is piped from curl.

A source checkout is optional: `./install.sh` installs the same independent
runtime, so you can delete that checkout afterward. The former `--venv-dir`,
`VENV_DIR`, `REPO_URL`, and `INSTALL_DIR` bootstrap overrides are no longer used;
the user install has the fixed paths above. If a previous bootstrap left a Git
checkout in `~/.local/share/shruti`, move that directory aside before installing.
Preferences and the saved key remain in `~/.config/shruti`.

What setup asks:

- Gemini API key (hidden input)
- Preferred hotkey (default `Ctrl+Space`)

Hotkey behavior after setup:

- Press hotkey once: start recording
- Press hotkey again: stop and transcribe
- Press `Esc`: cancel current recording

Nothing runs in background while idle. On GNOME, setup binds the shortcut to
`~/.local/bin/shruti oneshot`. On other desktops, setup prints a command to bind
in your desktop's shortcut settings.

## Uninstall

```bash
shruti-uninstall
```

This removes the app, virtual environment, both commands, Shruti's GNOME shortcut,
and its idle runtime files. Other GNOME shortcuts are preserved. Stop any active
recording first and run uninstall from your desktop session.

**By default, preferences and your saved Gemini API key remain in
`~/.config/shruti/`.** To remove them together with the app:

```bash
shruti-uninstall --purge
```

If you already uninstalled and later want to purge the saved configuration/key,
use the standalone uninstaller (no checkout or app installation needed):

```bash
curl -fsSL https://raw.githubusercontent.com/creasac/shruti/master/uninstall.py | python3 - --purge
```

Purge deletes the local key file; it does not revoke the key at Google. System
packages are left installed because other programs may use them. Shortcuts you
created manually in another desktop must be removed there manually.

## Configuration

Files:

- `~/.config/shruti/config.toml`
- `~/.config/shruti/credentials.toml`

API key location:

- Stored only in `~/.config/shruti/credentials.toml`

To remove your key:

```bash
rm -f ~/.config/shruti/credentials.toml
```

To remove all Shruti config data:

```bash
rm -rf ~/.config/shruti
```

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

## Development checks

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh bootstrap.sh
```

## License

MIT. See [LICENSE](LICENSE).
