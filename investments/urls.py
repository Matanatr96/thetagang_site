from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:option_id>/", views.detail, name="details"),
    path('api/create-transaction/', views.create_transaction, name='create_transaction'),
    path('api/get-securities/', views.get_securities, name='get_securities'),
]