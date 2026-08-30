import contextlib
import io
import json
import stat
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import shell_pack


class ShellPackRenderTests(unittest.TestCase):
    def test_render_is_deterministic_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"

            manifest_one = shell_pack.render_pack(first)
            manifest_two = shell_pack.render_pack(second)

            self.assertEqual(manifest_one, manifest_two)
            self.assertEqual(manifest_one["palette_count"], 36)
            self.assertEqual(manifest_one["adapter_count"], 7)
            first_files = {
                path.relative_to(first): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)
            self.assertEqual(
                len(list((first / "noctalia" / "palettes").glob("*.json"))),
                36,
            )
            self.assertEqual(
                len(list((first / "noctalia" / "templates" / "shadcn").iterdir())),
                7,
            )
            self.assertEqual(
                len(list((first / "rendered" / "graphite").iterdir())),
                7,
            )

    def test_generated_config_is_valid_sanitized_toml(self):
        config = shell_pack._shell_config()

        parsed = tomllib.loads(config)

        self.assertEqual(parsed["theme"]["source"], "custom")
        self.assertNotIn("bar", parsed)
        self.assertNotIn("dock", parsed)
        self.assertNotIn("desktop_widgets", parsed)
        self.assertEqual(len(parsed["theme"]["templates"]["user"]), 7)
        self.assertIsNone(shell_pack.SECRET_RE.search(config))
        self.assertNotIn(str(Path.home()), config)

    def test_verify_detects_modified_pack_file(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "pack"
            shell_pack.render_pack(pack)
            palette = pack / "noctalia" / "palettes" / "graphite.json"
            palette.write_text("{}")

            errors = shell_pack.verify_pack(pack)

            self.assertTrue(any("checksum mismatch" in error for error in errors))

    def test_verify_detects_modified_rendered_output(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "pack"
            shell_pack.render_pack(pack)
            output = pack / "rendered" / "graphite" / "gtk3.css"
            output.write_text("tampered")

            errors = shell_pack.verify_pack(pack)

            self.assertTrue(any("checksum mismatch" in error for error in errors))

    def test_render_removes_stale_files_and_verify_rejects_unmanifested_files(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "pack"
            shell_pack.render_pack(pack)
            stale = pack / "stale.txt"
            stale.write_text("stale")

            errors = shell_pack.verify_pack(pack)

            self.assertTrue(any("unmanifested pack file" in error for error in errors))
            shell_pack.render_pack(pack)
            self.assertFalse(stale.exists())
            self.assertEqual(shell_pack.verify_pack(pack), [])


class XdgResolutionTests(unittest.TestCase):
    def test_noctalia_override_wins(self):
        env = {
            "NOCTALIA_CONFIG_HOME": "/profiles/test",
            "XDG_CONFIG_HOME": "/xdg/config",
        }

        self.assertEqual(
            shell_pack.noctalia_config_dir(env, Path("/home/test")),
            Path("/profiles/test/noctalia"),
        )

    def test_xdg_and_home_fallbacks(self):
        self.assertEqual(
            shell_pack.noctalia_config_dir({"XDG_CONFIG_HOME": "/xdg/config"}),
            Path("/xdg/config/noctalia"),
        )
        self.assertEqual(
            shell_pack.noctalia_config_dir({}, Path("/home/test")),
            Path("/home/test/.config/noctalia"),
        )

    def test_relative_xdg_roots_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            shell_pack.xdg_config_home({"XDG_CONFIG_HOME": "relative/config"})
        with self.assertRaisesRegex(ValueError, "absolute"):
            shell_pack.xdg_config_home({"NOCTALIA_CONFIG_HOME": "relative/profile"})


class InstallLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.pack = root / "pack"
        self.config = root / "config" / "noctalia"
        shell_pack.render_pack(self.pack)

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_is_a_dry_run_and_does_not_mutate(self):
        before = list(Path(self.temp.name).rglob("*"))

        actions = shell_pack.plan_install(self.pack, self.config)

        after = list(Path(self.temp.name).rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse(self.config.exists())
        self.assertEqual(sum(action["action"] == "create" for action in actions), 44)
        self.assertFalse(any(action["action"].endswith("output") for action in actions))

    def test_apply_is_idempotent_and_verify_matches(self):
        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="first")
        second = shell_pack.apply_pack(self.pack, self.config, timestamp="second")

        self.assertEqual(backup, self.config / shell_pack.BACKUP_ROOT / "first")
        self.assertIsNone(second)
        self.assertEqual(shell_pack.verify_pack(self.pack, self.config), [])
        backups = list((self.config / shell_pack.BACKUP_ROOT).iterdir())
        self.assertEqual(backups, [self.config / shell_pack.BACKUP_ROOT / "first"])

    def test_overwrite_is_backed_up_and_rollback_restores(self):
        palette = self.config / "palettes" / "graphite.json"
        palette.parent.mkdir(parents=True)
        palette.write_text('{"user": true}\n')

        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="backup")
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertNotEqual(palette.read_text(), '{"user": true}\n')
        self.assertEqual(
            (backup / "files" / "palettes" / "graphite.json").read_text(),
            '{"user": true}\n',
        )

        restored = shell_pack.rollback(self.config, backup)

        self.assertEqual(restored, backup)
        self.assertEqual(palette.read_text(), '{"user": true}\n')
        self.assertFalse((self.config / shell_pack.MANAGED_CONFIG).exists())
        self.assertFalse((self.config / "palettes" / "mono.json").exists())
        self.assertFalse((self.config.parent / "gtk-3.0" / "noctalia.css").exists())

    def test_adapter_outputs_are_left_to_noctalia_activation(self):
        output = self.config.parent / "gtk-3.0" / "noctalia.css"
        output.parent.mkdir(parents=True)
        output.write_text("user gtk theme\n")

        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="outputs")
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(output.read_text(), "user gtk theme\n")

    def test_refuses_unmanaged_config_without_any_mutation(self):
        self.config.mkdir(parents=True)
        target = self.config / shell_pack.MANAGED_CONFIG
        target.write_text('[theme]\nmode = "light"\n')

        with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "ambiguous config merge"):
            shell_pack.apply_pack(self.pack, self.config, timestamp="unsafe")

        self.assertEqual(target.read_text(), '[theme]\nmode = "light"\n')
        self.assertFalse((self.config / "palettes").exists())
        self.assertFalse((self.config / shell_pack.BACKUP_ROOT).exists())

    def test_refuses_symlink_target(self):
        self.config.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text("sentinel")
        palette_dir = self.config / "palettes"
        palette_dir.mkdir()
        (palette_dir / "graphite.json").symlink_to(outside)

        with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "symlink"):
            shell_pack.apply_pack(self.pack, self.config, timestamp="unsafe")

        self.assertEqual(outside.read_text(), "sentinel")

    def test_refuses_symlinked_target_ancestor(self):
        real_root = Path(self.temp.name) / "real-config"
        real_root.mkdir()
        linked_root = Path(self.temp.name) / "linked-config"
        linked_root.symlink_to(real_root, target_is_directory=True)
        config = linked_root / "noctalia"

        with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "symlink ancestor"):
            shell_pack.apply_pack(self.pack, config, timestamp="unsafe")

        self.assertEqual(list(real_root.iterdir()), [])

    def test_rollback_refuses_to_overwrite_post_apply_user_edits(self):
        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="conflict")
        assert backup is not None
        palette = self.config / "palettes" / "graphite.json"
        palette.write_text('{"user": "edited after apply"}\n')

        with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "rollback conflict"):
            shell_pack.rollback(self.config, backup)

        self.assertEqual(palette.read_text(), '{"user": "edited after apply"}\n')
        self.assertTrue((self.config / shell_pack.MANAGED_CONFIG).exists())

    def test_rollback_rejects_metadata_for_unmanaged_target(self):
        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="tampered")
        assert backup is not None
        record_path = backup / "rollback.json"
        record = json.loads(record_path.read_text())
        record["changes"][0]["path"] = "unmanaged.txt"
        record_path.write_text(json.dumps(record))
        unmanaged = self.config / "unmanaged.txt"
        unmanaged.write_text("keep")

        with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "rollback metadata"):
            shell_pack.rollback(self.config, backup)

        self.assertEqual(unmanaged.read_text(), "keep")

    def test_apply_reverses_all_mutations_when_a_write_fails(self):
        existing = self.config / shell_pack.MANAGED_CONFIG
        existing.parent.mkdir(parents=True)
        existing.write_text(shell_pack.OWNER_MARKER + "\nold\n")
        existing.chmod(0o640)
        original_secure_write = shell_pack._secure_atomic_write

        def fail_during_install(root_fd, parent_fd, relative, data, *, mode):
            if relative == Path("palettes") / "amber-minimal.json":
                raise OSError("simulated write failure")
            return original_secure_write(
                root_fd, parent_fd, relative, data, mode=mode
            )

        with mock.patch.object(
            shell_pack, "_secure_atomic_write", side_effect=fail_during_install
        ):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                shell_pack.apply_pack(self.pack, self.config, timestamp="interrupted")

        self.assertEqual(existing.read_text(), shell_pack.OWNER_MARKER + "\nold\n")
        self.assertEqual(stat.S_IMODE(existing.stat().st_mode), 0o640)
        self.assertFalse((self.config / "palettes" / "amber.json").exists())

    def test_apply_refuses_parent_swap_without_writing_through_symlink(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        original_secure_write = shell_pack._secure_atomic_write
        swapped = False

        def swap_parent_before_write(root_fd, parent_fd, relative, data, *, mode):
            nonlocal swapped
            if not swapped and relative == Path("palettes") / "amber-minimal.json":
                swapped = True
                palettes = self.config / "palettes"
                held = self.config / "palettes-held"
                palettes.rename(held)
                palettes.symlink_to(outside, target_is_directory=True)
            return original_secure_write(
                root_fd, parent_fd, relative, data, mode=mode
            )

        with mock.patch.object(
            shell_pack,
            "_secure_atomic_write",
            side_effect=swap_parent_before_write,
        ):
            with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "changed after validation"):
                shell_pack.apply_pack(self.pack, self.config, timestamp="parent-swap")

        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.config / shell_pack.MANAGED_CONFIG).exists())
        self.assertFalse((self.config / "palettes-held" / "amber-minimal.json").exists())

    def test_apply_and_rollback_preserve_existing_file_mode(self):
        palette = self.config / "palettes" / "graphite.json"
        palette.parent.mkdir(parents=True)
        palette.write_text('{"user": true}\n')
        palette.chmod(0o640)

        backup = shell_pack.apply_pack(self.pack, self.config, timestamp="modes")
        assert backup is not None
        self.assertEqual(stat.S_IMODE(palette.stat().st_mode), 0o640)

        shell_pack.rollback(self.config, backup)

        self.assertEqual(palette.read_text(), '{"user": true}\n')
        self.assertEqual(stat.S_IMODE(palette.stat().st_mode), 0o640)

    def test_cli_plan_reports_no_mutation(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = shell_pack.main(
                ["plan", "--pack-dir", str(self.pack), "--config-dir", str(self.config)]
            )

        self.assertEqual(result, 0)
        self.assertIn("dry-run only", stdout.getvalue())
        self.assertFalse(self.config.exists())

    def test_cli_apply_requires_explicit_flag(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = shell_pack.main(
                ["apply", "--pack-dir", str(self.pack), "--config-dir", str(self.config)]
            )

        self.assertEqual(result, 2)
        self.assertIn("explicit --apply flag", stderr.getvalue())
        self.assertFalse(self.config.exists())


class NoctaliaCommandTests(unittest.TestCase):
    def test_constructs_only_allowlisted_argv_commands(self):
        config = Path("/tmp/profile/noctalia")

        self.assertEqual(
            shell_pack.noctalia_command("validate", config_dir=config),
            ["noctalia", "config", "validate", str(config)],
        )
        self.assertEqual(
            shell_pack.noctalia_command("config-reload", config_dir=config),
            ["noctalia", "msg", "config-reload"],
        )
        self.assertEqual(
            shell_pack.noctalia_command("color-scheme", config_dir=config, palette="graphite"),
            ["noctalia", "msg", "color-scheme-set", "custom", "graphite"],
        )
        self.assertEqual(
            shell_pack.noctalia_command("templates-apply", config_dir=config),
            ["noctalia", "msg", "templates-apply"],
        )
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            shell_pack.noctalia_command("exec", config_dir=config)
        with self.assertRaisesRegex(ValueError, "unsafe palette"):
            shell_pack.noctalia_command(
                "color-scheme", config_dir=config, palette="graphite; touch /tmp/bad"
            )

    def test_activate_uses_argv_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "noctalia"
            palette = config / "palettes" / "graphite.json"
            palette.parent.mkdir(parents=True)
            palette.write_text('{"name": "graphite"}\n')
            (config / shell_pack.MANAGED_CONFIG).write_text(shell_pack._shell_config())
            with (
                mock.patch.dict(
                    shell_pack.os.environ,
                    {"NOCTALIA_CONFIG_HOME": str(config.parent)},
                    clear=True,
                ),
                mock.patch.object(shell_pack.subprocess, "run") as run,
            ):
                shell_pack.activate(config, "graphite")

        self.assertEqual(run.call_count, 4)
        self.assertTrue(all(call.kwargs == {"check": True, "shell": False} for call in run.call_args_list))
        self.assertTrue(all(isinstance(call.args[0], list) for call in run.call_args_list))

    def test_activate_rejects_palette_that_is_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "noctalia"
            config.mkdir()
            (config / shell_pack.MANAGED_CONFIG).write_text(shell_pack._shell_config())
            with (
                mock.patch.dict(
                    shell_pack.os.environ,
                    {"NOCTALIA_CONFIG_HOME": str(config.parent)},
                    clear=True,
                ),
                mock.patch.object(shell_pack.subprocess, "run") as run,
            ):
                with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "installed palette"):
                    shell_pack.activate(config, "graphite")

        run.assert_not_called()

    def test_cli_keeps_apply_and_live_activation_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "pack"
            config = Path(directory) / "config" / "noctalia"
            shell_pack.render_pack(pack)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = shell_pack.main(
                    [
                        "apply",
                        "--apply",
                        "--activate",
                        "graphite",
                        "--pack-dir",
                        str(pack),
                        "--config-dir",
                        str(config),
                    ]
                )

        self.assertEqual(result, 2)
        self.assertIn("separate activate command", stderr.getvalue())

    def test_activate_refuses_non_active_sandbox_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_root = root / "active"
            sandbox = root / "sandbox" / "noctalia"
            palette = sandbox / "palettes" / "graphite.json"
            palette.parent.mkdir(parents=True)
            palette.write_text('{"name": "graphite"}\n')
            (sandbox / shell_pack.MANAGED_CONFIG).write_text(shell_pack._shell_config())
            with (
                mock.patch.dict(
                    shell_pack.os.environ,
                    {"NOCTALIA_CONFIG_HOME": str(active_root)},
                    clear=True,
                ),
                mock.patch.object(shell_pack.subprocess, "run") as run,
            ):
                with self.assertRaisesRegex(shell_pack.UnsafeInstallError, "active Noctalia"):
                    shell_pack.activate(sandbox, "graphite")

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
