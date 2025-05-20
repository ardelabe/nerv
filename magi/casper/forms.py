from django import forms
from .models import InputData

class InputDataForm(forms.ModelForm):
    """
    Form for the user to enter the input data.
    """
    
    class Meta:
        model = InputData
        fields = ['file', 'text', 'prompt_type']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4}),
        }
