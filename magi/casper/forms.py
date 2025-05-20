from django import forms
from .models import InputData, PromptDefinition # Importe PromptDefinition

class InputDataForm(forms.ModelForm):
    # Remova as escolhas hardcoded, o campo prompt_type agora é uma ForeignKey
    # e Django renderizará um select box automaticamente.
    # Você pode querer adicionar um campo de texto adicional para a pergunta, se o prompt_type for 'question'.
    
    # Adicione um campo extra para a pergunta do usuário se o prompt for 'question'
    user_question = forms.CharField(
        max_length=500,
        required=False, # Não é sempre necessário
        help_text="Informe sua pergunta se o tipo de prompt for 'Question'."
    )

    class Meta:
        model = InputData
        fields = ['file', 'text', 'prompt_type', 'user_question'] # Inclua user_question aqui
        # widgets = {
        #     'prompt_type': forms.Select(choices=PromptDefinition.objects.values_list('prompt_type', 'prompt_type').order_by('prompt_type')),
        # }
        # O Django geralmente renderiza um Select automatically para ForeignKey,
        # mas você pode personalizar aqui se precisar.