from django.urls import path
from clinic.views.dashboard import DashboardStatisticsAPIView, DashboardAppointmentTodayAPIView, DashboardOptionsAPIView
from clinic.views.branches import ListCreateBranchesAPIViews, RetrieveUpdateDeleteBranchesAPIViews, RetrieveBranchOptionsAPIView
from clinic.views.procedures import ListCreateProceduresAPIViews, RetrieveUpdateDeleteProceduresAPIViews, RetrieveProcedureOptionsAPIView
from clinic.views.waiting_room import ListCreateWaitingRoomItemsAPIViews, UpdateDeleteWaitingRoomItemAPIViews,RetrieveWaitingRoomOptionsAPIView 
from clinic.views.inventory import (ListCreateInventoryAPIViews, RetrieveUpdateDeleteInventoryAPIViews,
                                  RetrieveInventoryOptionsAPIView)
from clinic.views.labs import (ListCreateLabsAPIView, RetrieveUpdateDeleteLabAPIView, ListCreateLabOrdersAPIView,
                               UpdateDeleteLabOrderAPIView, RetrieveLabOrdersOptionsAPIView)
from clinic.views.sterilization_logs import (ListCreateSterilizationLogsAPIView, UpdateDeleteSterilizationLogAPIView,
                                             RetrieveSterilizationLogsOptionsAPIView)


#Url patterns
urlpatterns = [
    #Dashboard urls
    path('dashboard/stats/', DashboardStatisticsAPIView.as_view(), name='dashboard_stats'),
    path('dashboard/appointments-today/', DashboardAppointmentTodayAPIView.as_view(), name='dashboard_appointments_today'),
    path('dashboard/options/', DashboardOptionsAPIView.as_view(), name='dashboard_options'),

    #Branches urls
    path('branches/', ListCreateBranchesAPIViews.as_view(), name='list_create_branches'),
    path('branches/<uuid:id>/', RetrieveUpdateDeleteBranchesAPIViews.as_view(), name='retrieve_update_delete_branch'),
    path('branches/options/', RetrieveBranchOptionsAPIView.as_view(), name='branches_options'),

    #Waiting room urls 
    path('waiting-room/', ListCreateWaitingRoomItemsAPIViews.as_view(), name='list_create_waiting_room_items'),
    path('waiting-room/<uuid:id>/', UpdateDeleteWaitingRoomItemAPIViews.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_waiting_room_item'),
    path('waiting-room/options/', RetrieveWaitingRoomOptionsAPIView.as_view(), name='waiting_room_options'),

    #Procedures urls
    path('procedures/', ListCreateProceduresAPIViews.as_view(), name='list_create_procedures'),
    path('procedures/<uuid:id>/', RetrieveUpdateDeleteProceduresAPIViews.as_view(), name='retrieve_update_delete_procedure'),
    path('procedures/options', RetrieveProcedureOptionsAPIView.as_view(), name='procedures_options'),

    #Inventory urls
    path('inventory/', ListCreateInventoryAPIViews.as_view(), name='list_create_inventory'),
    path('inventory/<uuid:id>/', RetrieveUpdateDeleteInventoryAPIViews.as_view(), name='retrieve_update_delete_inventory'),
    path('inventory/options/', RetrieveInventoryOptionsAPIView.as_view(), name='inventory_options'),

    #Labs urls
    path('labs/', ListCreateLabsAPIView.as_view(), name='list_create_labs'),
    path('labs/<uuid:id>/', RetrieveUpdateDeleteLabAPIView.as_view(), name='retrieve_update_delete_lab'),

    #Lab orders urls 
    path('lab-orders/', ListCreateLabOrdersAPIView.as_view(), name='list_create_lab_orders'),
    path('lab-orders/<uuid:id>/', UpdateDeleteLabOrderAPIView.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_lab_orders'),
    path('lab-orders/options/', RetrieveLabOrdersOptionsAPIView.as_view(), name='lab_orders_options'),

    #Sterilization logs urls 
    path('sterilization/', ListCreateSterilizationLogsAPIView.as_view(), name='list_create_sterilization_logs'),
    path('sterilization/<uuid:id>/', UpdateDeleteSterilizationLogAPIView.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_sterilization_log'),
    path('sterilization/options/', RetrieveSterilizationLogsOptionsAPIView.as_view(), name='sterilization_logs_options'),
]