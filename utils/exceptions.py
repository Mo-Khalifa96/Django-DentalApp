import logging
from django.http import Http404
from django.conf import settings
from rest_framework import status
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException, ErrorDetail
from django.db.models.deletion import ProtectedError, RestrictedError
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

#Exception for perio exams
class PerioExamLockedError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'PERIO_EXAM_LOCKED'
    default_detail = _('This exam can no longer be corrected because it was recorded on an older date. '
                       'Create a new exam instead to record current findings.')

#Exception for invalid phone numbers 
class InvalidPhoneNumberError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'INVALID_PHONE_NUMBER'
    default_detail = _("Patient's phone number is invalid or can't be reached on WhatsApp.")

#Exception for duplicate installment bill creation
class InstallmentBillExistsError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'INSTALLMENT_BILL_ALREADY_EXISTS'
    default_detail = _('An installment bill already exists for this treatment plan.')

#Exception for recreating/editing installment plan with paid installments
class InstallmentPlanInProgressError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'INSTALLMENT_PLAN_IN_PROGRESS'  #code=...
    default_detail = _('This installment plan cannot be modified or deleted because one or more installments have already been paid.')  #detail=

     #How this API Exception will be used:
     # Cannot change an installment plan with paid installments
     # Cannot delete an installment plan with paid installments


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
        return _integrity_error_handler(exc)

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
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail),
                        'conflictWith': data.get('conflictWith'),
                    }
                },
                status=exc.status_code,
            )
        
        if isinstance(exc, PerioExamLockedError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'PERIO_EXAM_LOCKED',
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail)
                    }
                },
                status=exc.status_code,
            )
        
        #Handle InstallmentPlanInProgressError
        if isinstance(exc, InstallmentPlanInProgressError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': exc.default_code,
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail)
                    }
                },
                status=exc.status_code,
            )
        
        #Handle InstallmentBillExistsError 
        if isinstance(exc, InstallmentBillExistsError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': exc.default_code,
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail),
                        'billId': data.get('billId'),
                        
                        # 'message': str(data.get('detail', exc.default_detail)), #TODO - confirm which one is right
                        # 'billId': str(data['billId']) if data.get('billId') else None,
                    }
                },
                status=exc.status_code,
            )
        
        #Handle WhatsAppAPIError
        if isinstance(exc, WhatsAppAPIError):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': getattr(exc, 'error_code', None) or 'WHATSAPP_API_ERROR',
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail)
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
                        'code': exc.default_code,
                        'message': str(data.get('detail') or exc.default_detail) if isinstance(data, dict) else str(exc.detail)
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
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



#Human-readable messages for specific named CheckConstraints — extend as you add more
CHECK_CONSTRAINT_MESSAGES = {
    'outbound_referral_single_target': _('A referral cannot be linked to both a system doctor and an outside referral source. Please provide one or neither.'),
}

def _integrity_error_handler(exc):
    '''Returns json response upon hitting an integrity error (differentiated by cause).'''

    #Django-level: on_delete=PROTECT/RESTRICT — no DB introspection needed
    if isinstance(exc, (ProtectedError, RestrictedError)):
        blocking_count = exc.protected_objects.count() if hasattr(exc, 'protected_objects') else None
        return Response({
                'success': False,
                'error': {
                    'code': 'PROTECTED_REFERENCE',
                    'message': _('This record cannot be deleted because it is still referenced by other records.'),
                    **({'referencedCount': blocking_count} if blocking_count is not None else {}),
                }
            }, status=status.HTTP_409_CONFLICT)

    #Raw DB-level integrity errors — introspect Postgres SQLSTATE via the wrapped driver exception
    pgcode = getattr(getattr(exc, '__cause__', None), 'pgcode', None)

    if pgcode == '23505':  #unique_violation
        return Response({
                'success': False,
                'error': {'code': 'UNIQUE_CONSTRAINT_VIOLATION', 'message': _('A record with this unique identifier already exists.')}
            }, status=status.HTTP_409_CONFLICT)

    if pgcode == '23514':  #check_violation
        constraint_name = getattr(getattr(exc.__cause__, 'diag', None), 'constraint_name', None)
        message = CHECK_CONSTRAINT_MESSAGES.get(constraint_name, _('This record violates a data integrity rule.'))
        return Response({
                'success': False,
                'error': {'code': 'CONSTRAINT_VIOLATION', 'message': message}
            }, status=status.HTTP_400_BAD_REQUEST)  #this is malformed input, not a state conflict

    if pgcode == '23503':  #foreign_key_violation
        return Response({
                'success': False,
                'error': {'code': 'INVALID_REFERENCE', 'message': _('A referenced record does not exist.')}
            }, status=status.HTTP_400_BAD_REQUEST)

    #Unknown integrity error — log it rather than guessing at a label
    logger.error(f'Unhandled IntegrityError (pgcode={pgcode}): {exc}')
    return Response({
            'success': False,
            'error': {'code': 'INTEGRITY_ERROR', 'message': _('A data integrity error occurred.')}
        }, status=status.HTTP_409_CONFLICT)



#older version integrity error handler
def _integrity_error_handler_OLDversion(exc=None):   #for later if you want to use str(exc) for the message
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
