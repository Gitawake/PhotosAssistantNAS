# Contributing

Run standard-library-only tests before submitting a change:

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public.py
python3 tools/package_source.py
```

Use synthetic media and fake usernames such as `test-user` in fixtures. Never commit private NAS addresses, account identifiers, passwords, OTPs, sessions, keys, source media, decoder binaries, downloaded packages or raw diagnostics.

A new Photos version requires evidence from a real NAS with a narrowly scoped synthetic item: missing result, generation, Photos acceptance, stop/start, uninstall and preservation of both originals and generated resources. State untested clients and formats explicitly.

Keep coordinator changes small and review privilege, file path, process lifetime and error handling implications. Changes to API authentication, root deployment, version checks, decoder isolation or dependency licenses need additional review.

Public binary releases are currently blocked by the pinned nonfree FFmpeg build. Do not add a workflow that uploads private build artifacts or requires NAS credentials. Refer to docs/distribution.md before proposing release automation.

The installed NAS application is separate from this development repository; tests and builds must not SSH into or update a user's NAS automatically.
