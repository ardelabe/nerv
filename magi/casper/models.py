from django.db import models

class InputData(models.Model):
    """
    Model to store the user's input data.
    """
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='arquivos/', blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    prompt_type = models.CharField(
        max_length=50,
        choices=[
            ('summary', 'Summary'),
            ('question', 'Question'),
            ('translation', 'Translation'),
            ('other', 'Other'),
        ],
        default='summary'
    )
    submission_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.file_name:
            return f"Data from {self.file_name}"
        else:
            return f"Text data submitted on {self.submission_date}"

class PromptDefinition(models.Model):
    """
    Model to store predefined prompts for AI analysis.
    """
    prompt_type = models.CharField(
        max_length=50,
        unique=True, # Garante que não haja tipos de prompt duplicados
        help_text="Tipo de prompt (e.g., summary, question, translation)"
    )
    prompt_text = models.TextField(
        help_text="O texto completo do prompt para a IA (e.g., 'Resuma o texto a seguir:')"
    )
    
    class Meta:
        verbose_name = "Definição de Prompt"
        verbose_name_plural = "Definições de Prompts"

    def __str__(self):
        return self.prompt_type

class InputData(models.Model):
    """
    Model to store the user's input data.
    """
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='arquivos/', blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    
    # Alterar prompt_type para ser uma ForeignKey para PromptDefinition
    # CASCADE significa que se uma PromptDefinition for deletada, o InputData relacionado também será.
    prompt_type = models.ForeignKey(
        PromptDefinition, 
        on_delete=models.SET_NULL, # Ou models.SET_DEFAULT, models.PROTECT, etc., dependendo da sua lógica.
                                    # SET_NULL é bom se você quiser manter o InputData mas remover o link ao prompt.
        null=True, 
        blank=True,
        related_name='input_data_entries', # Nome para o relacionamento inverso
        help_text="Tipo de prompt para análise (escolha uma definição predefinida)"
    )
    
    submission_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.file_name:
            return f"Data from {self.file_name}"
        else:
            return f"Text data submitted on {self.submission_date}"
        
"""PROMPT_DEFINITIONS = {
    'summary': "Por favor, resuma o seguinte texto de forma concisa e objetiva:",
    'question': "Com base no texto a seguir, responda a pergunta: ", # A pergunta do usuário será concatenada aqui.
    'translation': "Traduza o seguinte texto para o português do Brasil:", # Ou para outro idioma, dependendo da necessidade.
    'other': "Analise o seguinte conteúdo: " # Um prompt mais genérico.
}"""
