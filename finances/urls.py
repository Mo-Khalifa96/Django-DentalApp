from django.urls import path
from finances.views.tax_config import ClinicTaxConfigAPIView


urlpatterns = [
    #Clinical tax config urls
    path('invoices/tax-config/', ClinicTaxConfigAPIView.as_view(
            http_method_names=['get', 'post', 'put', 'delete', 'options']
        ), name='view_create_update_tax_config'),
    # path('invoices/options/', .as_view(), name='view_create_update_tax_config'),
]