from django.urls import path
from . import views  # Importa as views do seu aplicativo

app_name = 'casper' # Adicione esta linha

urlpatterns = [
    # Define as URLs para as views do seu aplicativo
    path('read_file/', views.read_file, name='read_file'),
    path('process_text/<int:id>/', views.process_text, name='process_text'),
    # Você pode adicionar mais URLs aqui para outras views do seu aplicativo
]