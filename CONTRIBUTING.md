# Contributing

Thanks for helping make Linux desktop theming more coherent.

## Development setup

The core generator uses Python 3 and the standard library. Native render
verification additionally requires Noctalia v5, and the release gate requires
Pyright. Clone the repository, create changes on a topic branch, and keep live
desktop installation separate from repository-local generation.

```bash
python3 forge.py --noctalia-dir out/palettes-test
python3 templates.py
python3 -m unittest discover -s tests -q
```

## Change guidelines

- Preserve the semantic token mapping in `mapping.md` and the component
  contract in `DESIGN.md`.
- Add or update regression tests for every behavior change.
- Keep generated files under `out/` out of commits.
- Do not add host-specific paths, monitor names, credentials, or pinned apps.
- Treat `apply`, `activate`, and rollback behavior as safety-critical.
- Avoid new runtime dependencies unless the benefit clearly justifies them.

Before opening a pull request, run `python3 verify_release.py` where the full
release toolchain is available. Explain any unavailable verification stage in
the pull request.

## Bug reports

Include the desktop environment, compositor, toolkit/app version, active
palette and mode, exact command, terminal output, and a screenshot when the
problem is visual. Remove personal information from screenshots and logs.
