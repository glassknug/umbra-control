import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import startup

class StartupTests(unittest.TestCase):
    def test_opt_in_snapshot_update_and_disable(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}):
            self.assertIsNone(startup.load())
            p = dict(name='Balanced', sensor='k10temp|Tctl', shortcut='1', points=[[35,75],[80,100]])
            startup.configure(p)
            self.assertEqual(startup.load()['name'], 'Balanced')
            config, entry = startup.paths()
            self.assertIn('--autostart', entry.read_text())
            self.assertIn('Terminal=false', entry.read_text())
            p['name'] = 'Quiet'
            self.assertEqual(startup.load()['name'], 'Balanced')
            startup.configure(p)
            self.assertEqual(startup.load()['name'], 'Quiet')
            startup.configure(None)
            self.assertFalse(entry.exists())
            self.assertFalse(config.exists())

    def test_invalid_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}):
            with self.assertRaises(ValueError):
                startup.configure(dict(name='Bad', sensor='', shortcut='', points=[[35,10],[80,100]]))
            self.assertIsNone(startup.load())
