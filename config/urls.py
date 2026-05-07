from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

handler404 = 'projects.views.handler404'
handler500 = 'projects.views.handler500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('projects.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
