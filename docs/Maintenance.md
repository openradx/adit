# Maintenance

## How to upgrade

Routine dependency updates arrive as [Renovate](https://docs.renovatebot.com/) pull requests (`renovate.json`): non-major Python and JavaScript updates and Docker digest updates are grouped, lock file maintenance runs weekly, and the `rev` pins in `.pre-commit-config.yaml` are bumped too (the local `uv run` hooks take their tool versions from `uv.lock`). Version ceilings (e.g. PostgreSQL 17, Python 3.13) are enforced via `packageRules`. These are the places that hold version pins, and what to do when Renovate does not cover a change:

- The Python package dependencies (normal dependencies and dev dependencies)
  - Check outdated Python packages: `uv run cli show-outdated` (check Python section in output)
  - `uv lock --upgrade` will update packages according to their version range in `pyproject.toml`
  - Other upgrades (e.g. major versions) must be upgraded by modifying the version range in `pyproject.toml` before calling `uv lock --upgrade`
  - The `adit-radis-shared` dependency is pinned to a Git tag in `[tool.uv.sources]` of `pyproject.toml`; bump the tag manually and run `uv lock`
- JavaScript dependencies
  - Check outdated JavaScript packages: `uv run cli show-outdated` (check NPM section in output)
  - `npm update` will update packages according to their version range in `package.json`
  - Other upgrades (e.g. major versions) must be upgraded by modifying the version range in `package.json` before calling `npm update`
  - After an upgrade run `uv run cli copy-statics`: it copies the `dcmjs`, `dicomweb-client`, and `dicom-web-anonymizer` builds from `node_modules` into `adit/upload/static/vendor` (`package.json` declares only `dicom-web-anonymizer`; `dcmjs` is pulled in as its dependency, and the `dicomweb-client` glob only matches when that package is installed). Check that the vendored files still work in the upload app. The CodeMirror files in `adit/mass_transfer/static/mass_transfer/vendor` are vendored by hand and are not touched by `copy-statics`
- Python and uv in `Dockerfile` that builds the container where ADIT runs in
  - The `postgresql-client-<version>` package installed there must match the major version of the `postgres` image in `docker-compose.base.yml`, otherwise `db-backup`/`db-restore` break
- Dependent services in `docker-compose.base.yml`, like PostgreSQL or the Orthanc test servers
- GitHub Codespaces development container dependencies in `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile`
- GitHub Actions `.github/workflows/ci.yml` dependencies
