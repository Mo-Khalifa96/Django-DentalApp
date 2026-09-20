from django.urls import path
from finances.views.tax_config import ClinicTaxConfigAPIView
from finances.views.invoices import (ListCreateInvoicesAPIView, RetrieveUpdateDeleteInvoiceAPIView,
                                     RetrieveInvoicesOptionsAPIView)
from finances.views.transactions import (ListCreateTransactionsAPIView, UpdateDeleteTransactionAPIView,
                                         RetrieveTransactionsOptionsAPIView)
from finances.views.bills import (ListCreateBillsAPIView, RetrieveUpdateDeleteBillAPIView, 
                                  AutogenerateInvoiceAPIView, RetrieveBillsOptionsAPIView)
from finances.views.insurance_providers import (ListCreateInsuranceProvidersAPIView, 
                                                RetrieveUpdateDeleteInsuranceProviderAPIView,
                                                RetrieveInsuranceProvidersOptionsAPIView)
from finances.views.installments import (GenerateInstallmentPlanAPIView, AutogenerateInstallmentsBillAPIView,
                                         ListInstallmentPlansAPIView, RetrieveUpdateDeletePatientInstallmentPlanAPIView, 
                                         UpdateDeleteInstallmentPlanAPIView, CreateInstallmentTransactionAPIView, 
                                         RetrieveInstallmentsOptionsAPIView)

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

    #Installments urls -- patient/treatment-scooped
    path('patients/<uuid:id>/treatment-plans/<uuid:treatmentId>/installments/generate/', 
         GenerateInstallmentPlanAPIView.as_view(), name='generate_installment_plan'),
    path('patients/<uuid:id>/treatment-plans/<uuid:treatmentId>/installments/',
         RetrieveUpdateDeletePatientInstallmentPlanAPIView.as_view(
             http_method_names=['get', 'patch', 'delete', 'options']
         ), name='retrieve_update_delete_patient_installment_plan'),
    path('patients/<uuid:id>/treatment-plans/<uuid:treatmentId>/installments/autogenerate-bill/', 
         AutogenerateInstallmentsBillAPIView.as_view(), name='autogenerate_installments_bill'),
    #Installments urls -- general
    path('installments/', ListInstallmentPlansAPIView.as_view(), name='list_installment_plans'),
    path('installments/<uuid:id>/', UpdateDeleteInstallmentPlanAPIView.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_installment_plan_general'),
    path('installments/<uuid:id>/autogenerate-bill/', AutogenerateInstallmentsBillAPIView.as_view(), name='autogenerate_installments_bill_general'),
    #Installments transactions url 
    path('installments/<uuid:id>/transactions/', CreateInstallmentTransactionAPIView.as_view(), name='create_installment_transaction'),
    #Installments options url
    path('installments/options/', RetrieveInstallmentsOptionsAPIView.as_view(), name='installments_options'),

    #Insurance providers urls
    path('insurance/providers/', ListCreateInsuranceProvidersAPIView.as_view(), name='list_create_providers'),
    path('insurance/providers/<uuid:providerId>/', RetrieveUpdateDeleteInsuranceProviderAPIView.as_view(), name='retrieve_update_delete_provider'),
    path('insurance/providers/options/', RetrieveInsuranceProvidersOptionsAPIView.as_view(), name='providers_options'),
]