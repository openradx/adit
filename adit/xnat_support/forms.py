from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Row, Column, Div, Button, HTML
from crispy_forms.bootstrap import StrictButton


def xnat_options_field(option_field_names: list, area_css_id="xnat-options"):
    option_fields = []
    for field_name in option_field_names:
        if "project_id" in field_name:
            btn_id = "btn-"+area_css_id+"-find-projects"
            option_fields.append(
                Div(
                    Row(
                        Column(
                            Field(field_name),
                        ),
                    ),
                    Row(
                        Column(
                            Button(
                                name="find_projects",
                                value="Find projects",
                                css_class="btn-secondary btn-sm",
                                css_id="btn-"+area_css_id+"-find-projects"
                            ),
                            css_class="col-md-2"
                        ),
                        Column(
                            style="overflow-y: scroll; max-height:100px; border: 1px solid #ced4da; border-radius: 0.25rem;",
                            css_id=area_css_id+"project-id-list",
                            css_class="col-md-10"
                        ),
                        style="margin-top: -10px; padding: 10px;"
                    ),
                    style="margin-bottom: 30px;"
                )
            )
        else:
            option_fields.append(
                Row(
                    Column(
                        Field(field_name),
                    ),
                ),
            )
    option_field_area = (
        Row(
            Column(
                Div(
                    Div(
                        StrictButton(
                            "XNAT options (optional)",
                            css_class="btn-link px-0",
                            css_id="advanced_xnat_options_toggle",
                            **{
                                "data-toggle": "collapse",
                                "data-target": "#advanced_xnat_options",
                                "aria-expanded": "true",
                                "aria-controls": "advancedXnatOptions",
                            },
                        ),
                        css_class="card-title mb-0",
                    ),
                    Div(
                        *option_fields,
                        css_class="show pt-1",
                        css_id="advanced_xnat_options",
                    ),
                    css_class="card-body p-2",
                ),
                css_class="card",
            ),
            css_class="px-1 mb-3",
            css_id=area_css_id,
            style="display: none",
        ),
    )

    return option_field_area[0]
