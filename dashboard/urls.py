from django.urls import path
from dashboard import views

urlpatterns = [
    path('', views.HubMainView.as_view(), name='hub_main_view'),
    path('connect/', views.HubMainView.as_view(), name='connect_new_hub'),

    path('<str:node_id>/remove',
         views.RemoveNode.as_view(),
         name='node_remove'),

     path('test/', views.TestView.as_view(), name='test_view'),



     #### ajax views
     path('discover', views.ajax_discover_nodes, name='ajax_discover_nodes'),
     path('test_connection', views.ajax_check_node_connection, name='ajax_check_node_connection'),
     path('check_for_nodes/',
          views.ajax_check_for_nodes,
          name='ajax_check_for_nodes'),
]