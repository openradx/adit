# TODO

## High Priority

- Type site.py (also in ADIT)
- Secure API view
  -- Create group that can use API
  -- Differentiate between users that can query data and modify data
- Improve TokenFactory (+ ADIT)
- Rename populate_db to populate_data
- <https://docs.vespa.ai/en/operations/docker-containers.html#mounting-persistent-volumes>
- Change maxHits and maxOffset for farer pagination
  -- <https://docs.vespa.ai/en/reference/query-api-reference.html#native-execution-parameters>
  -- <https://pyvespa.readthedocs.io/en/latest/reference-api.html#queryprofile>
- Check if we can get rid of wsgi.py (also in RADIS)
  -- <https://forum.djangoproject.com/t/adding-asgi-support-to-runserver/2446/26>
  -- <https://github.com/django/django/pull/16634/files>
- Allow to configure reference names using a database model
  -- Reference: name (unique), match (unique)
- Sidebar like in <https://cord19.vespa.ai/search?query=pain> with filters: Age, Gender, Modality, Study Description
- Remove unneeded templatetags

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

## Transfer to RADIS

- Rename populate_dev_db to populate_db
- .env files in project dir (instead of compose dir)
- Correct help in populate_dev_db command
- Delete reset_dev_db and add reset option to populate_dev_db
- globals.d.ts
- PageSizeSelectMixin improvements
