from django.urls import path
from finances.views.tax_config import ClinicTaxConfigAPIView
from finances.views.invoices import (ListCreateInvoicesAPIView, RetrieveUpdateDeleteInvoiceAPIView,
                                     RetrieveInvoicesOptionsAPIView)
from finances.views.transactions import (ListCreateTransactionsAPIView, UpdateDeleteTransactionAPIView,
                                         RetrieveTransactionsOptionsAPIView)
from finances.views.bills import (ListCreateBillsAPIView, RetrieveUpdateDeleteBillAPIView, 
                                  AutogenerateInvoiceAPIView, RetrieveBillsOptionsAPIView)
from finances.views.insurance_providers import (ListCreateInsuranceProvidersAPIView, RetrieveUpdateDeleteInsuranceProviderAPIView,
                                                RetrieveInsuranceProvidersOptionsAPIView)

#finances urls
urlpatterns = [
    #Clinical tax config urls
    path('invoices/tax-config/', ClinicTaxConfigAPIView.as_view(
            http_method_names=['get', 'post', 'put', 'delete', 'options']
        ), name='view_create_update_tax_config'),

    #Bills urls
    path('bills/', ListCreateBillsAPIView.as_view(), name='list_create_bills'),
    path('bills/<uuid:id>/', RetrieveUpdateDeleteBillAPIView.as_view(), name='retrieve_update_delete_bill'),
    path('bills/<uuid:id>/generate-invoice/', AutogenerateInvoiceAPIView.as_view(), name='autogenerate_invoice'),
    path('bills/options/', RetrieveBillsOptionsAPIView.as_view(), name='bills_options'),

    #Transactions urls 
    path('transactions/', ListCreateTransactionsAPIView.as_view(), name='list_create_transactions'),
    path('transactions/<uuid:id>/', UpdateDeleteTransactionAPIView.as_view(
        http_method_names=['patch', 'delete', 'options']
    ), name='update_delete_transaction'),
    path('transactions/options/', RetrieveTransactionsOptionsAPIView.as_view(), name='transactions_options'),

    #Invoices urls
    path('invoices/', ListCreateInvoicesAPIView.as_view(), name='list_create_invoices'),
    path('invoices/<uuid:id>/', RetrieveUpdateDeleteInvoiceAPIView.as_view(), name='retrieve_update_delete_invoice'),
    path('invoices/options/', RetrieveInvoicesOptionsAPIView.as_view(), name='invoices_options'),

    #Insurance providers urls
    path('insurance/providers/', ListCreateInsuranceProvidersAPIView.as_view(), name='list_create_providers'),
    path('insurance/providers/<uuid:providerId>/', RetrieveUpdateDeleteInsuranceProviderAPIView.as_view(), name='retrieve_update_delete_provider'),
    path('insurance/providers/options/', RetrieveInsuranceProvidersOptionsAPIView.as_view(), name='providers_options'),
]