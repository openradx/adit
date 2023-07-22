# TODO

## High Priority

- Cleanup icons and rename images from .html to .svg
- <https://docs.vespa.ai/en/operations/docker-containers.html#mounting-persistent-volumes>

## Fix

## Features

## Maybe

- Adjust the summary dynamic snippets of the search results
  -- <https://docs.vespa.ai/en/document-summaries.html>
  -- Unfortunately, ApplicationConfiguration does not allow to put the configuration inside the content cluster (see link above)
  --- <https://github.com/vespa-engine/pyvespa/blob/75c64ab144f98155387ff1f461632b889c19bd6e/vespa/package.py#L1490>
  --- <https://github.com/vespa-engine/pyvespa/blob/master/vespa/templates/services.xml>
  -- That's why we would need to manipulate the XML files ourselves (maybe with <https://docs.python.org/3/library/xml.etree.elementtree.html>)
  -- or simply wait for <https://github.com/vespa-engine/pyvespa/issues/520>
- Put an extra "indication" field into the schema
  -- Also must be included in the ranking expression, see <https://pyvespa.readthedocs.io/en/latest/getting-started-pyvespa.html#Define-ranking>
- Multi node Vespa example setup
  -- <https://github.com/vespa-engine/sample-apps/blob/master/examples/operations/multinode-HA/>
- Standalone logging server
  -- SigNoz <https://github.com/signoz/signoz>
  -- Loki <https://github.com/grafana/loki>
  -- ELK stack <https://github.com/deviantony/docker-elk>

## Transfer to ADIT

- .env files in project dir (instead of compose dir)
- Correct help in populate_dev_db command
- Delete reset_dev_db and add reset option to populate_dev_db
- default_auto_field = "django.db.models.BigAutoField" in apps.py
- Use bootstrap icons font instead of SVGs
- Improve copy-statics task
