## What and why

## Checklist

- [ ] `python3 -m unittest discover -s tests` passes
- [ ] New capabilities have a refusal test (the fake `herdr` argv log must not exist on a refused call)
- [ ] New tools are annotated (`read_only` / `destructive`) and documented in `docs/TOOLS.md`
- [ ] No new runtime dependencies, no secrets in logs or child environments
- [ ] Notes added under `## Unreleased` in `CHANGELOG.md`