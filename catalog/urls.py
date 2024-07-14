from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='catalog'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('check-stock/<int:product_id>/', views.check_stock, name='check_stock'),
    path('order/<int:product_id>/', views.submit_order, name='order'),
]