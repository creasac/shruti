import contextlib
import fcntl
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('uninstall', Path(__file__).parents[1] / 'uninstall.py')
uninstall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uninstall)


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.app = self.home / '.local/share/shruti'
        self.bin = self.home / '.local/bin'
        self.config = self.home / '.config/shruti'
        (self.app / 'venv/bin').mkdir(parents=True)
        self.bin.mkdir(parents=True)
        self.config.mkdir(parents=True)
        (self.app / 'venv/bin/shruti').touch()
        (self.app / 'uninstall.py').touch()
        (self.bin / 'shruti').symlink_to(self.app / 'venv/bin/shruti')
        (self.bin / 'shruti-uninstall').symlink_to(self.app / 'uninstall.py')
        self.key = self.config / 'credentials.toml'
        self.key.write_text('api_key = "test-only"\n')
        self.key.chmod(0o600)
        self.lock = self.home / 'oneshot.lock'
        self.pid = self.home / 'oneshot.pid'
        self.lock.touch()
        self.pid.write_text('12345')
        for patcher in (
            patch.object(Path, 'home', return_value=self.home),
            patch.object(uninstall, 'LOCK_PATH', self.lock),
            patch.object(uninstall, 'PID_PATH', self.pid),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_uninstall(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return uninstall.main(args)

    @patch.object(uninstall, 'remove_gnome_shortcut')
    def test_default_preserves_key_and_allows_later_standalone_purge(self, shortcut):
        self.assertEqual(self.run_uninstall([]), 0)
        shortcut.assert_called_once()
        self.assertEqual(self.key.read_text(), 'api_key = "test-only"\n')
        self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.app.exists())
        self.assertFalse((self.bin / 'shruti').is_symlink())
        self.assertFalse((self.bin / 'shruti-uninstall').is_symlink())
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.pid.exists())
        self.assertEqual(self.run_uninstall(['--purge']), 0)
        self.assertFalse(self.config.exists())
        self.assertEqual(self.run_uninstall(['--purge']), 0)

    @patch.object(uninstall, 'remove_gnome_shortcut')
    def test_purge_removes_config_but_not_unrelated_data_or_command(self, shortcut):
        other = self.home / 'unrelated.txt'
        other.write_text('keep me')
        (self.bin / 'shruti').unlink()
        (self.bin / 'shruti').write_text('another command')
        self.assertEqual(self.run_uninstall(['--purge']), 0)
        self.assertFalse(self.config.exists())
        self.assertEqual(other.read_text(), 'keep me')
        self.assertEqual((self.bin / 'shruti').read_text(), 'another command')

    @patch.object(uninstall, 'remove_gnome_shortcut', side_effect=RuntimeError('no desktop session'))
    def test_shortcut_failure_keeps_app_uninstaller_and_key(self, shortcut):
        self.assertEqual(self.run_uninstall(['--purge']), 1)
        self.assertTrue(self.app.exists())
        self.assertTrue(self.key.exists())
        self.assertTrue((self.bin / 'shruti-uninstall').exists())

    @patch.object(uninstall, 'remove_gnome_shortcut')
    def test_active_recording_blocks_removal(self, shortcut):
        with self.lock.open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_uninstall(['--purge']), 1)
        shortcut.assert_not_called()
        self.assertTrue(self.app.exists())
        self.assertTrue(self.key.exists())

    @patch.object(uninstall, 'remove_gnome_shortcut')
    def test_legacy_checkout_is_not_destroyed(self, shortcut):
        (self.app / '.git').mkdir()
        self.assertEqual(self.run_uninstall(['--purge']), 1)
        self.assertTrue(self.key.exists())
        shortcut.assert_not_called()


class ShortcutTests(unittest.TestCase):
    @patch.object(uninstall.shutil, 'which', return_value='/usr/bin/gsettings')
    def test_removes_only_shruti_and_resets_its_keys(self, which):
        other = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/'
        calls = []
        state = [other, uninstall.GNOME_BINDING_PATH]

        def settings(*args):
            calls.append(args)
            if args[0] == 'list-schemas':
                return uninstall.GNOME_SCHEMA
            if args[0] == 'get':
                return repr(state)
            if args[0] == 'set':
                state[:] = uninstall.ast.literal_eval(args[-1])
            return ''

        with patch.object(uninstall, 'gsettings', side_effect=settings):
            uninstall.remove_gnome_shortcut()
        self.assertEqual(state, [other])
        self.assertEqual(calls[-1], ('reset-recursively', f'{uninstall.GNOME_SCHEMA}.custom-keybinding:{uninstall.GNOME_BINDING_PATH}'))

    @patch.object(uninstall.shutil, 'which', return_value='/usr/bin/gsettings')
    @patch.object(uninstall, 'gsettings')
    def test_detects_silent_gsettings_write_failure(self, settings, which):
        settings.side_effect = [uninstall.GNOME_SCHEMA, repr([uninstall.GNOME_BINDING_PATH]), '', repr([uninstall.GNOME_BINDING_PATH])]
        with self.assertRaisesRegex(RuntimeError, 'did not save'):
            uninstall.remove_gnome_shortcut()

    @patch.object(uninstall, 'gsettings', return_value='@as []')
    def test_typed_empty_gvariant(self, settings):
        self.assertEqual(uninstall.get_bindings(), [])


if __name__ == '__main__':
    unittest.main()
