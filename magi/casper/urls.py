from django.urls import path
from . import views

app_name = 'casper'

urlpatterns = [
    path('read_file/', views.read_file, name='read_file'),
    path('process_text/<int:id>/', views.process_text, name='process_text'),
    path('send_to_ai_studio/', views.send_to_ai_studio, name='send_to_ai_studio'), # Adicione esta linha
]