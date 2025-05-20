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
