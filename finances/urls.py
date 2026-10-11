from django.urls import path
from finances.views.tax_config import ClinicTaxConfigAPIView
from finances.views.invoices import (ListCreateInvoicesAPIView, RetrieveUpdateDeleteInvoiceAPIView,
                                     RetrieveInvoicesOptionsAPIView)
from finances.views.accounts import (RetrievePatientAccountAPIView, ListPatientAccountsAPIView, 
                                     FinanceSummaryAPIView)
from finances.views.bills import (ListCreateBillsAPIView, RetrieveUpdateDeleteBillAPIView, 
                                  AutogenerateInvoiceAPIView, RetrieveBillsOptionsAPIView)
from finances.views.insurance_providers import (ListCreateInsuranceProvidersAPIView, 
                                                RetrieveUpdateDeleteInsuranceProviderAPIView,
                                                ListInsuranceProvidersStatisticsAPIView,
                                                RetrieveInsuranceProvidersOptionsAPIView)
from finances.views.transactions import (ListCreateTransactionsAPIView, RetrieveUpdateDeleteTransactionAPIView,
                                         CreateDepositTransactionAPIView, RefundTransactionAPIView, RequestCorrectionAPIView, 
                                         RetrieveTransactionsOptionsAPIView)
from finances.views.installments import (GenerateInstallmentPlanAPIView, AutogenerateInstallmentsBillAPIView,
                                         ListInstallmentPlansAPIView, RetrieveUpdateDeletePatientInstallmentPlanAPIView, 
                                         UpdateDeleteInstallmentPlanAPIView, CreateInstallmentTransactionAPIView,
                                         RetrieveUpdateDeleteInstallmentTransactionAPIView, RetrieveInstallmentsOptionsAPIView)

#finances urls
urlpatterns = [
    #Clinical tax config urls
    path('invoices/tax-config/', ClinicTaxConfigAPIView.as_view(
            http_method_names=['get', 'post', 'put', 'delete', 'options']
        ), name='view_create_update_tax_config'),

    #Financial summary url
    path('finance/summary/', FinanceSummaryAPIView.as_view(), name='finance_stats'),

    #Patient (financial) accounts url
    path('accounts/', ListPatientAccountsAPIView.as_view(), name='list_patient_accounts'),
    path('patients/<uuid:id>/account/', RetrievePatientAccountAPIView.as_view(), name='retrieve_patient_account'),

    #Bills urls
    path('bills/', ListCreateBillsAPIView.as_view(), name='list_create_bills'),
    path('bills/<uuid:id>/', RetrieveUpdateDeleteBillAPIView.as_view(), name='retrieve_update_delete_bill'),
    path('bills/<uuid:id>/generate-invoice/', AutogenerateInvoiceAPIView.as_view(), name='autogenerate_invoice'),
    path('bills/options/', RetrieveBillsOptionsAPIView.as_view(), name='bills_options'),

    #Transactions urls
    #transactions list/crud
    path('transactions/', ListCreateTransactionsAPIView.as_view(), name='list_create_transactions'),
    path('transactions/<uuid:id>/', RetrieveUpdateDeleteTransactionAPIView.as_view(
            http_method_names=['get', 'patch', 'delete', 'options']
        ), name='retrieve_update_delete_transaction'),
    #deposits
    path('transactions/deposit/', CreateDepositTransactionAPIView.as_view(), name='create_deposit_transaction'),
    #refunds
    path('transactions/<uuid:id>/refund/', RefundTransactionAPIView.as_view(
            http_method_names=['patch', 'options']
        ), name='refund_transaction'),
    #corrections
    path('transactions/<uuid:id>/correction/', RequestCorrectionAPIView.as_view(
            http_method_names=['patch', 'options']
        ), name='request_correction_to_transaction'),
    #options
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
    path('installments/<uuid:id>/transactions/<uuid:transactionId>/',
         RetrieveUpdateDeleteInstallmentTransactionAPIView.as_view(
             http_method_names=['get', 'put', 'delete', 'options']
        ), name='retrieve_update_delete_installment_transaction'),
    #Installments options url
    path('installments/options/', RetrieveInstallmentsOptionsAPIView.as_view(), name='installments_options'),

    #Insurance providers urls
    path('insurance/providers/', ListCreateInsuranceProvidersAPIView.as_view(), name='list_create_providers'),
    path('insurance/providers/<uuid:providerId>/', RetrieveUpdateDeleteInsuranceProviderAPIView.as_view(), name='retrieve_update_delete_provider'),
    path('insurance/providers/summary/', ListInsuranceProvidersStatisticsAPIView.as_view(), name='insurance_providers_stats'),
    path('insurance/providers/options/', RetrieveInsuranceProvidersOptionsAPIView.as_view(), name='providers_options'),
]
