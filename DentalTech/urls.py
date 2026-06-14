import os 
from django.conf import settings
from django.contrib import admin
from django.urls import path, include 
from django.http import HttpResponse
from django.conf.urls.static import static 


urlpatterns = [
    #path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/', include('clinic.urls')),
    path('api/', include('patients.urls')),
    path('api/', include('finances.urls')),
    path('api/', include('services.urls')),
    path('', lambda request: HttpResponse('HOME')),
    path('health/', lambda request: HttpResponse('OK')),
]


if settings.DEBUG:
    import debug_toolbar
    from drf_spectacular.views import (
     SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView   
    )

    #Development paths 
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),  
        path('swagger/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('swagger/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('swagger/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  
    ]

if settings.ENABLE_SILK:
    urlpatterns += [
        path('silk/', include('silk.urls', namespace='silk')),
    ]


#Serve media files during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

