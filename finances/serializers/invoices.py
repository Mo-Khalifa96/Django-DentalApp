import logging
from decimal import Decimal
from clinic.models import Branch
from django.db import transaction 
from rest_framework import serializers
from finances.models import Bill, Invoice
from finances.docs import bills_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.models import Patient, TreatmentPlan, Visit
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from finances.docs import list_bills_schema, retrieve_bills_schema
from services.translation.serializers import TranslatedChoiceField


