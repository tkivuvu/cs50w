from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Got something interesting to say?",
                    "id": "post-content",
                    "maxlength": "500"
                }
            )
        }
        labels = {"content": ""}

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()
        if not content:
            raise forms.ValidationError("Your posts cannot be empty.")
        return content
