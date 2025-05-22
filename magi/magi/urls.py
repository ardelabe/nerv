"""
URL configuration for magi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings # Importe settings
from django.conf.urls.static import static # Importe static
from django.views.generic import TemplateView # Importe TemplateView

def home(request):
    """
    View para exibir a página inicial personalizada.
    """
    return render(request, 'casper/home.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('casper/', include('casper.urls')),
    path('', TemplateView.as_view(template_name='base/home.html'), name='home'), # Página inicial simples
    path('melchior/', include('melchior.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
