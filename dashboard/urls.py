from django.urls import path
from dashboard import views

urlpatterns = [
    path('', views.HubMainView.as_view(), name='hub_main_view'),
    path('connect/', views.HubMainView.as_view(), name='connect_new_hub'),
    path('discover/<str:hub_id>',
         views.DiscoverNewNodes.as_view(),
         name='hub_discover'),
    path('<str:node_id>/remove',
         views.RemoveNode.as_view(),
         name='node_remove'),
    path('test/', views.TestView.as_view(), name='test_view')
]