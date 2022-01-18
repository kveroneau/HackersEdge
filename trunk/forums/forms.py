from django import forms
from forums.models import Post
from forums.lookups import ForumLookup
from selectable.forms.widgets import AutoCompleteWidget

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('subject', 'body', )

class ForumSearchForm(forms.Form):
    q = forms.CharField(
        label='Search Forums',
        widget=AutoCompleteWidget(ForumLookup),
        required=False,
    )
