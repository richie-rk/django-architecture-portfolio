from django import forms

from .models import Category, Enquiry


INPUT_CLASSES = (
    'w-full px-4 py-3 bg-transparent border border-border '
    'text-ink placeholder-muted '
    'focus:outline-none focus:border-accent transition-colors duration-200'
)


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={'class': INPUT_CLASSES, 'placeholder': 'Your name'}
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={'class': INPUT_CLASSES, 'placeholder': 'you@example.com'}
        ),
    )
    project_type = forms.ModelChoiceField(
        # Re-bound in __init__ so it sees Categories added after import.
        queryset=Category.objects.none(),
        required=False,
        empty_label='Select a project type',
        widget=forms.Select(attrs={'class': INPUT_CLASSES}),
    )
    message = forms.CharField(
        min_length=10,
        widget=forms.Textarea(
            attrs={
                'class': INPUT_CLASSES + ' min-h-[160px]',
                'placeholder': 'Tell us about your project',
                'rows': 6,
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project_type'].queryset = Category.objects.all().order_by('order', 'name')

    def save(self):
        return Enquiry.objects.create(
            name=self.cleaned_data['name'],
            email=self.cleaned_data['email'],
            project_type=self.cleaned_data.get('project_type'),
            message=self.cleaned_data['message'],
        )
