# nerv/magi/melchior/urls.py

from django.urls import path
from . import views

app_name = 'melchior' # <--- ADICIONE ESTA LINHA AQUI!

urlpatterns = [
    path('search/', views.melchior_search_view, name='melchior_search'), # URL para a busca do Melchior
    # Adicione mais URLs para Melchior conforme necessário
]