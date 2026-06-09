from django.urls import path
from finances.views.tax_config import ClinicTaxConfigAPIView
from finances.views.bills import (ListCreateBillsAPIView, RetrieveUpdateDeleteBillAPIView, 
                                  AutogenerateInvoiceAPIView, RetrieveBillsOptionsAPIView)


urlpatterns = [
    #Clinical tax config urls
    path('invoices/tax-config/', ClinicTaxConfigAPIView.as_view(
            http_method_names=['get', 'post', 'put', 'delete', 'options']
        ), name='view_create_update_tax_config'),
    # path('invoices/options/', .as_view(), name='view_create_update_tax_config'),

    #Bills urls
    path('bills/', ListCreateBillsAPIView.as_view(), name='list_create_bills'),
    path('bills/<uuid:id>/', RetrieveUpdateDeleteBillAPIView.as_view(), name='retrieve_update_delete_bill'),
    path('bills/<uuid:id>/generate-invoice/', AutogenerateInvoiceAPIView.as_view(), name='autogenerate_invoice'),
    path('bills/options/', RetrieveBillsOptionsAPIView.as_view(), name='bills_options'),
]