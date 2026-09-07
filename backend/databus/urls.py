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

import re

from django.contrib import admin
from django.urls import URLPattern, URLResolver, path, include, re_path
from django.conf import settings
from django.views.static import serve
import os

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("", include("website.urls")),
    path("api/", include("api.urls")),
    path("feed/", include("feed.urls")),
]

serve_static_flag = os.environ.get("DJANGO_SERVE_STATIC", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
if settings.DEBUG or serve_static_flag:
    # NOTE: intentionally not using django.conf.urls.static.static() here --
    # that helper has its own internal `if not settings.DEBUG: return []`
    # guard, which silently ignores DJANGO_SERVE_STATIC whenever DEBUG=False
    # (i.e. always in production). Wiring django.views.static.serve directly
    # bypasses that guard so the flag actually works outside DEBUG, which is
    # required in production since compose.prod.yml has no separate static
    # file server (nginx/whitenoise) in front of Django.
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")),
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(settings.STATIC_URL.lstrip("/")),
            serve,
            {"document_root": settings.STATIC_ROOT},
        ),
    ]
