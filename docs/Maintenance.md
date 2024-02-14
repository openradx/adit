# Maintenance

## How to upgrade

There are different things that can be upgraded:

- The python package dependencies (normal dependencies and dev dependencies)
  -- Check outdated Python packages: `inv show-outdated` (check Python section in output)
  -- `poetry update` will update packages according to their version range in `pyproject.toml`
  -- Other upgrades (e.g. major versions) must be upgraded by modifying the version range in `pyproject.toml` before calling `poetry update`
- Javascript dependencies
  -- Check outdated Javascript packages: `inv show-outdated` (check Javascript section in output)
  -- `npm update` will update packages according to their version range in `package.json`
  -- Other upgrades (e.g. major versions) must be upgraded by modifying the version range in `packages.json` before calling `npm update`
  -- After an upgrade make sure the files in `static/vendor` still link to the correct files in `node_modules`1
- Python and Poetry in `Dockerfile` that builds the container where RADIS runs in
- Dependent services in `docker-compose.base.yml`, like PostgreSQL or Vespa database
- Gitpod development container dependencies in `.gitpod.Dockerfile`
- Github Codespaces development container dependencies in `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile`
