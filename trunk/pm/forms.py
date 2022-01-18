from django import forms
from pm.models import TodoItem
from help_center.models import Guide
from htmlchecker import HTMLChecker

class TodoForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = ('title', 'description', 'category',)

class IdeaForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = ('title', 'description',)

class GuideForm(forms.ModelForm):
    class Meta:
        model = Guide
        fields = ('title', 'topic', 'content',)
    def clean_content(self):
        data = self.cleaned_data['content']
        parser = HTMLChecker()
        parser.feed(data)
        if not parser.okay:
            raise forms.ValidationError('Only p, b, i, and strong HTML tags supported!')
        return data
