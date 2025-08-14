import markdown2
import random
from django import forms
from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse

from . import util


class NewEntryForm(forms.Form):
    title = forms.CharField(
        label="Page Title",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Python"}))
    content = forms.CharField(
        label="Markdown Content",
        widget=forms.Textarea(attrs={"class":"form-control", "rows":12, "placeholder": "# Heading\n\nYour content in **Markdown**..."}))

class EditEntryForm(forms.Form):
    content = forms.CharField(
        label="Markdown Content",
        widget=forms.Textarea(attrs={"class": "form-control", "rows":12})
    )


def index(request):
    return render(request, "encyclopedia/index.html", {
        "entries": util.list_entries()
    })


def entry(request, title):
    for name in util.list_entries():
        if name.lower() == title.lower():
            title = name
            break
    else:
        return render(
            request,
            "encyclopedia/error.html",
            {"title": title, "message": "The entry provided was not found."},
            status=404
        )
    md_content = util.get_entry(title)
    if md_content is None:
        return render(
            request,
            "encyclopedia/error.html",
            {"title": title, "message": "The entry provided was not found."},
            status=404
        )
    html_content = markdown2.markdown(md_content, extras=[
        "strike"
    ])
    return render(
        request,
        "encyclopedia/entry.html",
        {"title": title, "content": html_content}
    )  

    
def search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return render(
            request,
            "encyclopedia/error.html",
            {"title": "Search Error", "message": "No query was provided."}
        )
    
    entries = util.list_entries()
        
    for name in entries:
        if name.lower() == query.lower():
            return redirect(reverse("encyclopedia:entry", args=[name]))
    
    results = [name for name in entries if query.lower() in name.lower()]
    
    return render(
            request,
            "encyclopedia/search.html",
            {"query": query, "results": results}
        )

            
def new_page(request):
    if request.method == "POST":
        form = NewEntryForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data["title"].strip()
            content = form.cleaned_data["content"] 
            
            existing_titles = util.list_entries()
            if any(title.casefold() == e.casefold() for e in existing_titles):
                form.add_error("title", "An entry with this title already exists")
                return render(request, "encyclopedia/new.html", {"form": form})
            util.save_entry(title, content)
            return redirect(reverse("encyclopedia:entry", args=[title]))
        else:
            return render(request, "encyclopedia/new.html", {"form":form})
    else:
        return render(request, "encyclopedia/new.html", {"form": NewEntryForm()})


def edit_page(request, title):
    existing_title = util.get_entry(title)
    if existing_title is None:
        raise Http404("The entry was not found.")
    
    if request.method == "POST":
        form = EditEntryForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data["content"]
            util.save_entry(title, content)
            return redirect(reverse("encyclopedia:entry", args=[title]))
    else:
        form = EditEntryForm(initial={"content":existing_title})
    
    return render(request, "encyclopedia/edit.html", {
        "title": title,
        "form":form
    })
    
    
def random_page(request):
    existing_entries = util.list_entries()
    if not existing_entries:
        return render(
            request, "encyclopedia/index.html",{
                "entries": [],
                "message": "There are no entries yet please create one to start."
            })
    existing_titles = random.choice(existing_entries)
    return redirect(reverse("encyclopedia:entry", args=[existing_titles]))