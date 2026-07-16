# Release checklist

Use this checklist for a release candidate; it does not publish, tag or change repository visibility.

- [ ] `uv lock --check` passes on Python 3.11.
- [ ] Core-only and each optional framework extra install in fresh environments.
- [ ] Ruff format and lint, strict mypy and the complete test suite pass.
- [ ] Offline smoke, tutorials, patterns, approval modes and case-study variants pass.
- [ ] Documentation, notebooks, comparison and reproducibility checks pass.
- [ ] The public-content audit finds no credentials, private files, machine paths, model weights or prohibited binaries.
- [ ] Comparison inputs and deterministic metrics match the documented contract.
- [ ] Optional real-model and slow tests are either reported or explicitly recorded as not run.
- [ ] Compatibility claims name only platforms actually observed.
- [ ] `git diff --check` passes and the intended release tree is reviewed.
- [ ] Software citation metadata matches the release version and repository URL.
- [ ] A maintainer creates the commit, tag and archive only after review.
