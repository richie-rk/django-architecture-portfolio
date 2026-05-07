from django.urls import path

from . import views


app_name = 'projects'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('projects/', views.projects_list, name='list'),
    path('projects/<slug:slug>/', views.project_detail, name='detail'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
]
