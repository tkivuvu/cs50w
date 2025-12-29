from decimal import Decimal
from django import forms
from .models import Listing, Category, Comment

class ListingForm(forms.ModelForm):
    new_category = forms.CharField(
        required=False, max_length=64, label="Or add a new category"
    )

    class Meta:
        model = Listing
        fields = [
            "title", "description", "starting_bid", "image_url", "category"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}),
            "starting_bid": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "image_url": forms.URLInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.order_by("name")
        self.fields["category"].empty_label = "- Select a category -"
        self.fields["new_category"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Or add a new category"})

    def clean_starting_bid(self):
        amt = self.cleaned_data["starting_bid"]
        if amt is None or amt <= 0:
            raise forms.ValidationError("Starting bid must be greater than 0.")
        return amt

    def clean(self):
        cleaned = super().clean()
        cate = cleaned.get("category")
        new_cate =cleaned.get("new_category")
        if cate and new_cate:
            raise forms.ValidationError(
                "Choose an existing category or add a new one, not both.")
        cleaned["new_category"] = new_cate
        return cleaned

    def save(self, commit=True, owner=None):
        cate_instance = super().save(commit=False)
        new_cat_name = (self.cleaned_data.get("new_category") or "").strip()
        if new_cat_name:
            cat_obj, _ = Category.objects.get_or_create(name=new_cat_name)
            cate_instance.category = cat_obj
        if not cate_instance.category:
            other, _ = Category.objects.get_or_create(name="Other")
            cate_instance.category = other
        if owner is not None:
            cate_instance.owner = owner
        if commit:
            cate_instance.save()
        return cate_instance

class BidForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0.01", "step":"0.01"}))

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Write a Comment..."}
            )
        }
