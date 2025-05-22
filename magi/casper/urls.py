# nerv/magi/casper/urls.py

from django.urls import path
from . import views # Importa as views do aplicativo atual

app_name = 'casper' # Define o namespace da aplicação

urlpatterns = [
    # A URL para a página inicial do Casper
    path('', views.casper_home_view, name='casper_home'), 
    
    # Suas URLs existentes do Casper
    # path('read_file/', views.read_file, name='read_file'),
    path('process_text/<int:id>/', views.process_text, name='process_text'),
    path('send_to_ai_studio/', views.send_to_ai_studio, name='send_to_ai_studio'),
]