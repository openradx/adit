from vespa.package import ApplicationPackage, Field

app_package = ApplicationPackage(name="radis")
schema = app_package.schema
assert schema is not None
schema.add_fields(
    Field(
        name="pacs_aet",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="pacs_name",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="patient_id",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="study_uid",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="accession_number",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="study_description",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="study_datetime",
        type="long",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="series_uid",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="modalities",
        type="array<string>",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="instance_uid",
        type="string",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="references",
        type="array<string>",
        indexing=["attribute", "summary"],
    ),
    Field(
        name="content",
        type="string",
        indexing=["attribute", "summary"],
    ),
)
