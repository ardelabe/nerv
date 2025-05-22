# nerv/magi/melchior/models.py

from django.db import models
from django.core.validators import FileExtensionValidator

class Documento(models.Model):
    """
    Modelo para armazenar informações sobre os documentos carregados.
    """
    TIPO_DOCUMENTO_CHOICES = [
        ('PDF', 'PDF'),
        ('HTML', 'HTML'),
        ('OUTRO', 'Outro'), # Caso tenhamos outros tipos no futuro
    ]

    HIERARQUIA_NORMA_CHOICES = [
        ('CONSTITUICAO', 'Constituição'),
        ('LEI_FEDERAL', 'Lei Federal'),
        ('DECRETO_FEDERAL', 'Decreto Federal'),
        ('LEI_ESTADUAL', 'Lei Estadual'),
        ('DECRETO_ESTADUAL', 'Decreto Estadual'),
        ('LEI_MUNICIPAL', 'Lei Municipal'),
        ('RESOLUCAO', 'Resolução'),
        ('DECRETO_MUNICIPAL', 'Decreto Municipal'),
        ('PORTARIA', 'Portaria'),
        ('NORMA_TECNICA', 'Norma Técnica'),
        ('OUTRO', 'Outro'),
        ('NAO_APLICAVEL', 'Não Aplicável'),
    ]

    STATUS_DOCUMENTO_CHOICES = [
        ('VIGENTE', 'Vigente'),
        ('REVOGADO', 'Revogado'),
        ('PARCIALMENTE_REVOGADO', 'Parcialmente Revogado'),
        ('PENDENTE_ANALISE', 'Pendente de Análise'),
    ]

    nome_arquivo = models.CharField(max_length=255, unique=True, help_text="Nome original do arquivo.")
    arquivo = models.FileField(
        upload_to='documentos/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'html'])],
        help_text="Upload do arquivo PDF ou HTML."
    )
    tipo_documento = models.CharField(
        max_length=10,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='OUTRO',
        help_text="Tipo do arquivo (PDF, HTML, etc.)."
    )
    data_upload = models.DateTimeField(auto_now_add=True, help_text="Data e hora do upload do documento.")
    data_publicacao = models.DateField(null=True, blank=True, help_text="Data de publicação da norma (se aplicável).")
    data_vigencia = models.DateField(null=True, blank=True, help_text="Data de início de vigência da norma (se aplicável).")
    hierarquia = models.CharField(
        max_length=50,
        choices=HIERARQUIA_NORMA_CHOICES,
        default='NAO_APLICAVEL',
        help_text="Nível hierárquico da norma legal (se aplicável)."
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_DOCUMENTO_CHOICES,
        default='PENDENTE_ANALISE',
        help_text="Status de vigência do documento (Vigente, Revogado, etc.)."
    )
    # Campo para armazenar o texto completo extraído do documento antes de chunking
    texto_completo_extraido = models.TextField(blank=True, null=True, help_text="Texto completo extraído do documento.")

    def __str__(self):
        return self.nome_arquivo

class Chunk(models.Model):
    """
    Modelo para armazenar os pedaços de texto (chunks) de cada documento,
    seus embeddings e informações sobre antinomias.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='chunks', help_text="Documento ao qual este chunk pertence.")
    conteudo_original = models.TextField(help_text="O pedaço de texto original do documento.")
    conteudo_tratado = models.TextField(help_text="O pedaço de texto após a aplicação das regras de antinomia.")
    embedding = models.BinaryField(blank=True, null=True, help_text="O vetor de embedding do conteúdo tratado.")
    ordem_no_documento = models.IntegerField(help_text="Ordem do chunk dentro do documento original.")
    relevancia_antinomia = models.FloatField(default=0.0, help_text="Pontuação para indicar a relevância em relação a antinomias (0 a 1).")
    data_revisao_antinomia = models.DateTimeField(null=True, blank=True, help_text="Data da última revisão manual ou automática da antinomia.")
    # Exemplo de campo para referenciar a norma revogadora, se aplicável
    revogado_por_chunk = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chunks_revogados',
        help_text="Referência a outro chunk que revoga este (se aplicável)."
    )
    # Pode-se adicionar um campo booleano para indicar se o chunk foi considerado inválido devido a uma antinomia
    is_valido_apos_antinomia = models.BooleanField(default=True, help_text="Indica se o chunk é válido após a resolução de antinomias.")


    class Meta:
        # Garante que não haverá chunks duplicados para o mesmo documento e ordem
        unique_together = ('documento', 'ordem_no_documento')
        ordering = ['documento', 'ordem_no_documento'] # Ordem padrão para chunks

    def __str__(self):
        return f"Chunk {self.ordem_no_documento} de {self.documento.nome_arquivo}"