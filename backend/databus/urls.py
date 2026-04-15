"""
URL configuration for databus project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("website.urls")),
    path("api/", include("api.urls")),
    path("schedule_engine/", include("schedule_engine.urls")),
]

serve_static_flag = os.environ.get("DJANGO_SERVE_STATIC", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
if settings.DEBUG or serve_static_flag:
    # For debugging purposes, serve media and static files through Django.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
