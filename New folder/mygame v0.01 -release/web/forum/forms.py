"""
web/forum/forms.py
"""

from django import forms


class NewThreadForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Thread title…", "autocomplete": "off"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Write your post…", "rows": 8}),
    )


class ReplyForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Write your reply…", "rows": 6}),
    )


class EditPostForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Edit your post…", "rows": 6}),
    )
