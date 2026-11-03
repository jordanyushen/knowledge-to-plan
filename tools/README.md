# Build and integrity checks

These scripts use the Python standard library. Run them from the repository root.
Install `requirements.txt` first so course/example generation also has IANA
timezone data on Windows or hosts without system timezone data.

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/check_examples.py
python3 tools/verify_release.py
python3 tools/build_release.py --release-date 2026-11-04
```

`check_examples.py` copies the skill to a temporary directory, rebuilds the
baseline and STEM example there, and compares all four checked-in HTML/JSON
files byte for byte. It never rewrites the checked-in examples. After deliberately
changing the renderer, regenerate the actual examples before checking them.

`build_release.py` dynamically packages the complete `knowledge-to-plan/` folder
(excluding caches), plus root `LICENSE*`, `NOTICE*`, `COPYING*` and
`requirements*.txt`. It writes `manifest.json`, the selected ZIP and
`dist/SHA256SUMS`. ZIP paths, permissions, timestamps and file order are fixed;
entries are stored without compression to avoid platform zlib differences.
Identical source bytes and release dates produce identical artifacts.

`verify_release.py` checks the complete source inventory, each size/hash, archive
hash, checksum file, exact ZIP entry list, CRC and extracted bytes. It rejects
extra, missing, duplicate or modified archive entries. It does not regenerate
files to hide stale artifacts. Documentation, CI, evaluation fixtures and npm
development dependencies remain in the repository rather than the installed
skill ZIP.

An adopted `LICENSE`, `LICENSE.md` or `LICENSE.txt` must be at the root or inside
the skill for a release build/check. Proposed licensing drafts are not adopted
licenses. Until licensing is decided, local checks may explicitly use:

```sh
python3 tools/build_release.py --output /tmp/ktp-release --allow-unlicensed
python3 tools/verify_release.py --release-root /tmp/ktp-release --allow-unlicensed
```

That override reports `release_ready: false`; it verifies artifact integrity and
does not authorize redistribution. Regular CI permits this integrity-only mode;
tagged-release CI additionally requires the adopted license without an override.
The presence of a file is a packaging gate, not a legal review or confirmation of
third-party content rights.

`--root` selects another source checkout. `--output` (build) and `--release-root`
(verify) allow checking a temporary artifact set without replacing the repository
manifest or ZIP. Without `--release-date`, the builder retains the existing
manifest date so routine rebuilding is deterministic.

Browser fixtures are built by `prepare_e2e.py` into ignored `.e2e/site/` only.
See [`tests/e2e/README.md`](../tests/e2e/README.md) for browser checks and the
configured Mac's shell-launch restriction.
