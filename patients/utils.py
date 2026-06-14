import re 
from decimal import Decimal
from django.conf import settings
from datetime import datetime, date
from patients.validators import VALID_FDI_TEETH
from rest_framework.exceptions import ValidationError


###
#Utility functions and other useful variables 
#Valid teeth choices
TEETH_CHOICES = [(n, n) for n in sorted(VALID_FDI_TEETH)]

#Custom function to normalize phone number for storing
def normalize_phone_number(code, phone):
    #Normalize country code to 00XX format
    code = code.strip().replace(' ', '')
    if code.startswith('00'):
        code = '+' + code[2:]
    elif not code.startswith('+'):
        code = '+' + code

    #Strip formatting characters
    phone = re.sub(r'[\s\-\(\)]', '', phone.strip())

    #Strip country code from phone if present in any format
    code_00 = '00' + code[1:]
    if phone.startswith(code):
        phone = phone[len(code):]  #if starts with code with '+'
    elif phone.startswith(code_00):
        phone = phone[len(code_00):]  #if starts with code with '00'

    #Strip trunk prefix zeros
    phone = phone.lstrip('0')

    return code, phone


# #Custom function to calculate percentages 
# def calculate_percentage(vals, total):
#     if total == 0:
#         return [0 for _ in range(len(vals))] if isinstance(vals, list) else 0
#     if isinstance(vals, (int, float, Decimal)):
#         return round((vals / total) * 100, 2)
#     else:
#         return [round((val / total) * 100, 2) for val in vals]


# #Custom function to query parameters for date range
# def get_date_queryparam(request, param_name) -> date | None:
#     query_date = request.query_params.get(param_name)
#     if not query_date:
#         return None
#     try:
#         return datetime.strptime(query_date, '%Y-%m-%d').date()
#     except ValueError:
#         raise ValidationError(f"Invalid date format for '{param_name}'. Expected YYYY-MM-DD.")
