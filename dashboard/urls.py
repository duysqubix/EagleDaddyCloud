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
     path('diag_report', views.ajax_diagnostics_report, name='ajax_diagnostics_report'),
     path('diag_rcv', views.ajax_diagnostics_rcv, name='ajax_diagnostics_rcv'),
     path('check_for_nodes/',
          views.ajax_check_for_nodes,
          name='ajax_check_for_nodes'),
]