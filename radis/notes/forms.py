from django import forms

from .models import Note


class NoteEditForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ("text",)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["text"].label = ""

    def clean_text(self) -> str:
        return self.cleaned_data["text"].strip()
