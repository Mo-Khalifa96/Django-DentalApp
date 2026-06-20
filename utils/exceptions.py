import logging
from django.http import Http404
from django.conf import settings
from rest_framework import status
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException, ErrorDetail
from django.utils.translation import gettext_lazy as _
from services.whatsapp.exceptions import WhatsAppAPIError


#Instantiate logger for debugging 
logger = logging.getLogger('debugging_logger')


#SPECIAL-CASE EXCEPTIONS 
#Exception for appointment conflicts 
class AppointmentConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'APPOINTMENT_CONFLICT'
    default_detail = _('This appointment conflicts with an existing one.')


#Exception for invalid phone numbers 
class InvalidPhoneNumberError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'INVALID_PHONE_NUMBER'
    default_detail = _("Patient's phone number is invalid or not registered on WhatsApp.")


#############


#GLOBAL EXCEPTION HANDLER 
#Define global exception handler 
def DentalTechExceptionHandler(exc, context):  
    '''Main (global) exception handler for the system.'''
    #Let DRF convert Http404 and Django's PermissionDenied first
    response = exception_handler(exc, context)

    # print('DEBUG:', exc)
    
    #Handle Integrity error gracefully
    if isinstance(exc, IntegrityError):
        return _integrity_error_handler()

    if response is not None:
        #extract response data 
        data = response.data

        #Handle special case errors
        #Handle AppointmentConflictError
        if isinstance(exc, AppointmentConflictError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'APPOINTMENT_CONFLICT',
                        'message': 'Time slot is already booked.',
                        'conflictWith': data.get('conflictWith'),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        
        #Handle WhatsAppAPIError
        if isinstance(exc, WhatsAppAPIError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': exc.error_code or 'WHATSAPP_API_ERROR',
                        'message': str(exc.detail),
                    }
                },
                status=exc.status_code,
            )

        #Handle InvalidPhoneNumberError
        if isinstance(exc, InvalidPhoneNumberError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'INVALID_PHONE_NUMBER',
                        'message': "Patient's phone number is invalid or not registered on WhatsApp.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        ##Handle standard DRF exceptions##
        #Exceptions with a 'detail' key
        if isinstance(data, dict) and 'detail' in data:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': _extract_code(exc),
                        'message': str(data['detail']),
                    }
                },
                status=response.status_code,
            )

        #Validation errors — dict or list without 'detail' key
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Validation failed.',
                    'fields': _extract_messages(data),
                }
            },
            status=response.status_code,
        )
        
    
    #Unhandled exception (500 Server Error)
    logger.error('Unhandled exception -- 500 Server Error', exc_info=exc)
    if settings.DEBUG:
        return None  #let Django's debug page show
    else:
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'SERVER_ERROR',
                    'message': 'A server error occurred.',
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

#Define helper functions for message and code extraction
def _extract_code(exc):
    '''Extracts a single uppercase string code from any exception type.'''
    try:
        codes = exc.get_codes()
        
        if isinstance(codes, list):
            return str(codes[0]).upper()
        elif isinstance(codes, dict):
            try:
                return str(codes['code']).upper()
            except (KeyError, TypeError):
                return 'ERROR'
        return str(codes).upper()
    
    except Exception:
        return 'NOT_FOUND' if isinstance(exc, Http404) else 'ERROR'

def _extract_messages(messages):
    '''Normalizes field messages to a single string regardless of input type.'''
    if isinstance(messages, ErrorDetail):
        return str(messages)

    #Handle dict-nested field errors
    if isinstance(messages, dict):
        #standard:
        # if len(messages) == 1 and 'non_field_errors' in messages:
        #     return {
        #         'nonFieldErrors': _extract_messages(messages['non_field_errors'])
        #     }

        #collapse non_field_errors into single string message
        if len(messages) == 1 and 'non_field_errors' in messages:
            return _extract_messages(messages['non_field_errors'])
        

        #Handle validation errors for field errors
        return {
            field: _extract_messages(value)
            for field, value in messages.items()
        }

    #Handle list-nested error messages 
    if isinstance(messages, list):
        normalized_messages = [_extract_messages(item) for item in messages]
        #Flatten only plain message lists, not nested serializer lists
        if all(not isinstance(item, (dict, list)) for item in normalized_messages):
            return normalized_messages[0] if len(normalized_messages) == 1 else normalized_messages
        return normalized_messages

    #Fallback 
    return str(messages)

def _integrity_error_handler(exc=None):   #for later if you want to use str(exc) for the message
    '''Returns json response upon hitting integrty error.'''
    return Response(
            {
                'success': False,
                'error': {
                    'code': 'UNIQUE_CONSTRAINT_VIOLATION',
                    'message': 'A record with this unique identifier already exists.',
                }
            },
            status=status.HTTP_409_CONFLICT,  #409 for duplicate/conflict issues
        )
