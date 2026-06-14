from django.conf import settings


if settings.DEBUG:
    from users.models import User
    from rest_framework import filters
    from django_filters import CharFilter, ChoiceFilter, DateFilter, BooleanFilter
    from django_filters.rest_framework import DjangoFilterBackend
    from drf_spectacular.extensions import OpenApiFilterExtension
    from users.utils import category_patterns

    field_map = {'patient__name': 'patientName', 'doctor__name': 'doctorName', 
                'procedure__name': 'procedureName', 'lab__name': 'labName',
                'branch__name': 'branchName', 'treatment_items__procedureName': 'procedureName',
                'invoice_items__description': 'itemDescription'}
    
    CHAR_SEARCH_FIELDS = {
        'ListCreateSterilizationLogsAPIView': ['instrumentSets'],
        'ListCreateVisitsAPIView': ['procedures'],
    }

    class QueryingFilterExtension(OpenApiFilterExtension):
        '''Extension for handling custom django-filter fields in Swagger docs.'''
        target_class = 'django_filters.rest_framework.DjangoFilterBackend'
        priority = 3
        
        def get_schema_operation_parameters(self, auto_schema, *args, **kwargs):
            '''Override to handle choice filters with dynamic choices'''
            
            parameters = []
            
            #Get the filterset class
            if hasattr(auto_schema.view, 'filterset_class'):
                filterset_class = auto_schema.view.filterset_class
            else:
                filter_backend = DjangoFilterBackend()
                filterset_class = filter_backend.get_filterset_class(
                    auto_schema.view, 
                    auto_schema.view.get_queryset()
                )
            
            if filterset_class:
                #Create filterset instance to access dynamic choices
                try:
                    filterset_instance = filterset_class(queryset=auto_schema.view.get_queryset())
                except:
                    try:
                        filterset_instance = filterset_class()
                    except:
                        return []
                
                for filter_name, filter_field in filterset_instance.filters.items():
                    parameter = self._get_filter_parameter(filter_name, filter_field)
                    if parameter:
                        parameters.append(parameter)
            
            return parameters
        
        def _get_filter_parameter(self, filter_name, filter_field):
            '''Convert a django-filter field to an OpenAPI parameter'''
            
            #Handle ChoiceFilter with dynamic choices
            if isinstance(filter_field, ChoiceFilter):
                choices = []
                
                #Get choices from the field
                if hasattr(filter_field.field, 'choices') and filter_field.field.choices:
                    if callable(filter_field.field.choices):
                        try:
                            choices = list(filter_field.field.choices())
                        except:
                            choices = []
                    else:
                        choices = list(filter_field.field.choices)
                
                #Extract choice values
                enum_values = [str(choice[0]) for choice in choices if choice[0]] if choices else None
                description = f'<b>Filter by `{filter_name}`</b>'
                
                # if choices and len(choices) <= 6:
                #     choice_descriptions = [f'* `{choice[0]}` - {choice[1]}' for choice in choices if choice[0]]
                #     if choice_descriptions:
                #         description += f'\n\n{chr(10).join(choice_descriptions)}'
                
                if choices and len(choices) > 10:
                    enum_values = enum_values[:10]

                return {
                    'name': filter_name,
                    'in': 'query',
                    'schema': {
                        'type': 'string',
                        'enum': enum_values,
                    },
                    'description': description,
                    'required': getattr(filter_field.field, 'required', False)
                }

            #Handle date filters documentation
            if isinstance(filter_field, DateFilter):
                lookup_expr = getattr(filter_field, 'lookup_expr')
                field_name = getattr(filter_field, 'field_name', filter_name)

                lookup_descriptions = {
                    'gte': f'Filter by {field_name} on or after this date.',
                    'lte': f'Filter by {field_name} on or before this date.',
                    'gt': f'Filter by {field_name} after this date.',
                    'lt': f'Filter by {field_name} before this date.',
                    'exact': (f'Filter by exact {field_name} date.' 
                               if not field_name.lower().endswith('date')
                               else 'Filter by exact date.'),
                }

                return {
                    'name': filter_name,
                    'in': 'query',
                    'schema': {
                        'type': 'string',
                        'format': 'date',
                        # 'example': '2026-05-05',
                    },
                    'description': lookup_descriptions.get(
                        lookup_expr,
                        f'Filter by {field_name} using {lookup_expr}.'
                    ),
                    'required': getattr(filter_field.field, 'required', False)
                }
            
            # #Handle char filters documentation
            # if isinstance(filter_field, CharFilter):
                lookup_expr = getattr(filter_field, 'lookup_expr', 'exact')
                lookup_descriptions = {
                    'icontains': 'Case-insensitive substring match.',
                    'contains':  'Case-sensitive substring match.',
                    'exact':     'Exact match.',
                    'istartswith': 'Case-insensitive prefix match.',
                    'startswith':  'Case-sensitive prefix match.',
                }

                description = (
                    f'<b>Filter by `{filter_name}`</b> — '
                    f'{lookup_descriptions.get(lookup_expr, f"Lookup: {lookup_expr}")}'
                )
                return {
                    'name': filter_name,
                    'in': 'query',
                    'schema': {
                        'type': 'string',
                    },
                    'description': description,
                    'required': getattr(filter_field.field, 'required', False)
                }

            #Handle boolean filters documentation
            if isinstance(filter_field, BooleanFilter):
                field_name = getattr(filter_field, 'field_name', filter_name)
                return {
                    'name': filter_name,
                    'in': 'query',
                    'schema': {
                        'type': 'boolean',
                    },
                    'description': f'<b>Filter by `{filter_name}`</b>',
                    'required': getattr(filter_field.field, 'required', False)
                }

            #For other fields, return None to use default behavior
            return None

    class SearchFilterExtension(OpenApiFilterExtension): 
        '''Extension for handling SearchFilter with better descriptions'''
        target_class = 'rest_framework.filters.SearchFilter'
        priority = 2
        
        def get_schema_operation_parameters(self, auto_schema, *args, **kwargs):
            '''Override to provide better search parameter description'''
            if not hasattr(auto_schema.view, 'search_fields'):
                return []
            
            #get fields from 'search_fields' on view
            search_fields = getattr(auto_schema.view, 'search_fields', [])

            #Handle char filters
            view_name = auto_schema.view.__class__.__name__
            search_fields += CHAR_SEARCH_FIELDS.get(view_name, [])

            #exit if no search fields are found
            if not search_fields:
                return []

            #clean up field names
            clean_fields = [field_map.get(field, field) for field in search_fields]
            clean_fields = [f'<b>{field}</b>' for field in clean_fields]

            #convert to one full string
            search_fields_str = ', '.join(clean_fields)

            #filter backend
            filter_backend = filters.SearchFilter()
            
            return [{
                'name': filter_backend.search_param,
                'in': 'query',
                'schema': {'type': 'string'},
                'description': f'Search by fields: {search_fields_str}',
                'required': False
            }]

    class OrderingFilterExtension(OpenApiFilterExtension):
        '''Extension for handling CustomOrderingFilter with better descriptions'''
        target_class = 'utils.filters.CustomOrderingFilter'
        priority = 1
        
        def get_schema_operation_parameters(self, auto_schema, *args, **kwargs):
            if not hasattr(auto_schema.view, 'ordering_fields'):
                return []
            
            ordering_fields = getattr(auto_schema.view, 'ordering_fields', [])
            if not ordering_fields:
                return []
            
            #Clean up field names
            clean_fields = []
            for field in ordering_fields:
                # base = field.split('__')[0] if '__' in field else field
                clean_fields.append(field_map.get(field, field))
                        
            return [
                {
                    'name': 'sortBy',
                    'in': 'query',
                    'schema': {'type': 'string', 'enum': clean_fields},
                    'description': f'Sort by fields',
                    'required': False
                },
                {
                    'name': 'sortOrder',
                    'in': 'query',
                    'schema': {'type': 'string', 'enum': ['asc', 'desc']},
                    'description': 'Sort direction: asc (default) or desc',
                    'required': False
                }
            ]


    #Define postprocessing hook 
    def response_structure_postprocessing_hook(result, generator, request, public):
        for path, methods in result['paths'].items():
            for method, operation in methods.items():
                if 'responses' not in operation:
                    continue 
                
                is_excluded = False if '/auth/me/' in path else any([pattern in path for pattern in ['/auth/', '/roles/', '/permissions/', '/options/']])
                if is_excluded:
                    continue

                method = method.upper()

                if method == 'DELETE':
                    #Document typical error responses 
                    _add_error_responses(operation)
                    if '/appointments/' in path:
                        _wrap_cancel_appointment_response(operation)
                    continue 

                if method == 'GET':
                    if 'dashboard/appointments-today/' in path:
                        _wrap_special_pagination_responses_with_metadata(path, result, operation)
                        continue

                    #Document typical error responses 
                    _add_error_responses(operation)

                    has_pagination = (operation.get('parameters') and str(operation['operationId']).endswith('_list'))
                    has_page_pagination = has_pagination and any(param.get('name') == 'page' for param in operation.get('parameters', []))
                    is_cursor = has_pagination and any(param.get('name') == 'cursor' for param in operation.get('parameters', []))

                    if is_cursor:
                        continue

                    if has_page_pagination:
                        if 'treatment-plans' not in path:
                            _wrap_paginated_responses_with_metadata(path, result, operation)
                        else:
                            _wrap_special_pagination_responses_with_metadata(path, result, operation)
                    else:
                        if 'treatment-plans' not in path:
                            _wrap_get_responses_with_metadata(result, operation)
        
                else:
                    #for POST/PUT/PATCH responses 
                    #document validation responses
                    _add_validation_error_responses(operation, path)
                    
                    #document success response 
                    _wrap_success_responses(result, operation)
        
        return result


    def _wrap_paginated_responses_with_metadata(path, result, operation):
        '''Hook to include userPermissions metadata in all paginated list responses'''

        perm_category = _get_category_from_path(path)
        perm_category = 'sidebar' if not perm_category else perm_category
        user_permissions = list(User.USER_PERMISSIONS_DICT['sidebar']) + list(User.USER_PERMISSIONS_DICT[perm_category])
        user_permissions = list(dict.fromkeys(user_permissions))
        properties = {item: {'type': 'boolean'} for item in user_permissions}

        for status_code, response in operation['responses'].items():
            if 200 <= int(status_code) < 300 and 'content' in response:
                for media_type, content in response['content'].items():
                    if 'schema' in content:
                        original_schema = content['schema']

                        #Create paginated response structure
                        content['schema'] = {
                            'type': 'object',
                            'properties': {
                                'success': {'type': 'boolean', 'example': True},
                                'data': {
                                    'type': 'array',
                                    'items': _extract_item_schema_from_reference(original_schema, result)
                                },
                                'pagination': {
                                    'type': 'object',
                                    'properties': {
                                        'page': {'type': 'integer', 'description': 'Current page number'},
                                        'limit': {'type': 'integer', 'description': 'Items per page'},
                                        'total': {'type': 'integer', 'description': 'Total number of items'},
                                        'totalPages': {'type': 'integer', 'description': 'Total number of pages'},
                                        'hasNext': {'type': 'boolean', 'description': 'Has next page'},
                                        'hasPrev': {'type': 'boolean', 'description': 'Has previous page'}
                                    }
                                },
                                'links': {
                                    'type': 'object',
                                    'properties': {
                                        'next': {'type': 'string', 'nullable': True, 'format': 'uri', 'description': 'Next page link'},
                                        'previous': {'type': 'string', 'nullable': True, 'format': 'uri', 'description': 'Previous page link'}
                                    }
                                },
                                'metadata': {
                                    'type': 'object',
                                    'properties': {
                                        'userPermissions': {
                                            'type': 'object',
                                            'description': 'Dictionary with user permissions (boolean).',
                                            'properties': properties
                                        }
                                    }
                                }
                            }
                        }

        return result


    def _wrap_special_pagination_responses_with_metadata(path, result, operation):
        '''Hook to include userPermissions metadata in custom paginated response.
            Used for dashboard/appointments-today/ and /treatment-plans/ pagination.'''

        perm_category = _get_category_from_path(path)
        perm_category = 'sidebar' if not perm_category else perm_category
        user_permissions = list(User.USER_PERMISSIONS_DICT['sidebar']) + list(User.USER_PERMISSIONS_DICT[perm_category])
        user_permissions = list(dict.fromkeys(user_permissions))
        properties = {item: {'type': 'boolean'} for item in user_permissions}


        for status_code, response in operation['responses'].items():
            if 200 <= int(status_code) < 300 and 'content' in response:
                for media_type, content in response['content'].items():
                    if 'schema' in content:
                        original_schema = content['schema']

                        data = {
                                'type': 'array',
                                'items': _extract_item_schema_from_reference(original_schema, result)
                            }

                        #Create paginated response structure
                        content['schema'] = {
                            'type': 'object',
                            'properties': {
                                'success': {'type': 'boolean', 'example': True},
                                'data': data,
                                'metadata': {
                                    'type': 'object',
                                    'properties': {
                                        'userPermissions': {
                                            'type': 'object',
                                            'description': 'Dictionary with user permissions (boolean).',
                                            'properties': properties
                                        }
                                    }
                                }
                            }
                        }

        return result


    def _wrap_get_responses_with_metadata(result, operation):
        '''Hook to include userPermissions metadata in all relevant responses.'''
    
        for status_code, response in operation['responses'].items():
            if 200 <= int(status_code) < 300 and 'content' in response:
                for media_type, content in response['content'].items():
                    if 'schema' in content:
                        original_schema = content['schema']
                        schema_name = original_schema['$ref'].split('/')[-1]
                        resolved_schema = result['components']['schemas'][schema_name]
                        resolved_schema = resolved_schema['properties']
                        content['schema'] = {
                            'type': 'object',
                            'properties': {
                                'success': {'type': 'boolean', 'example': True},
                                'data': {
                                    'type': 'object',
                                    'properties': resolved_schema
                                },
                                'metadata': {
                                    'type': 'object',
                                    'readOnly': True,
                                    'properties': {
                                        'userPermissions': {
                                            'type': 'object',
                                            'description': 'Basic permissions for side/bottom bar icons.',
                                            'properties': {
                                                'view.calender': {'type': 'boolean'},
                                                'view.waitingRoom': {'type': 'boolean'},
                                                'view.patients': {'type': 'boolean'},
                                                'view.appointments': {'type': 'boolean'},
                                                'view.procedures': {'type': 'boolean'},
                                                'view.inventory': {'type': 'boolean'},
                                                'view.labs': {'type': 'boolean'},
                                                'view.labOrders': {'type': 'boolean'},
                                                'view.bills': {'type': 'boolean'},
                                                'view.transactions': {'type': 'boolean'},
                                                'view.invoices': {'type': 'boolean'},
                                                'view.doctorSchedules': {'type': 'boolean'},
                                                'view.sterilizationLogs': {'type': 'boolean'},
                                                'view.recalls': {'type': 'boolean'},
                                                'view.clinicalAnalytics': {'type': 'boolean'},
                                                'view.financialAnalytics': {'type': 'boolean'},
                                                'view.settings': {'type': 'boolean'},
                                                'view.preferences': {'type': 'boolean'}
                                            },
                                        },
                                    }
                                }
                            }
                        }
        return result


    def _wrap_success_responses(result, operation):
        for status_code, response in operation['responses'].items():
            if 200 <= int(status_code) < 300 and 'content' in response:
                for media_type, content in response['content'].items():
                    if 'schema' in content:
                        original_schema = content['schema']

                        if '$ref' in original_schema:
                            schema_name = original_schema['$ref'].split('/')[-1]
                            resolved_properties = result['components']['schemas'][schema_name].get('properties', {})
                        else:
                            resolved_properties = original_schema.get('properties', original_schema)

                        content['schema'] = {
                            'type': 'object',
                            'properties': {
                                'success': {'type': 'boolean', 'example': True},
                                'data': {
                                    'type': 'object',
                                    'properties': resolved_properties
                                }
                            }
                        }
        return result


    def _wrap_cancel_appointment_response(operation):
        '''Documents the cancel appointment endpoint request body and response.'''
        operation['requestBody'] = {
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'reason': {
                                'type': 'string',
                                'example': 'Patient cancelled due to emergency.',
                                'description': 'Optional reason for cancellation.'
                            }
                        }
                    }
                }
            },
            'required': False
        }
        operation['responses']['200'] = {
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'success': {'type': 'boolean', 'example': True},
                            'message': {'type': 'string', 'example': 'Appointment cancelled successfully.'}
                        }
                    }
                }
            }
        }
        operation['responses'].pop('204', None)


    def _add_error_responses(operation):
        '''Documents the standard error response structure across all operations.'''

        error_codes = {
            '401': 'Authentication required',
            '403': 'Permission denied',
            '404': 'Not found',
        }

        error_schema_dict = {
            '401': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'NOT_AUTHENTICATED'},
                            'message': {'type': 'string', 'example': "Authentication credentials were not provided."},
                        }
                    }
                }
            },
            '403': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'PERMISSION_DENIED'},
                        'message': {'type': 'string', 'example': "You do not have permission to perform this action."},
                        }
                    }
                }
            }, 
            '404': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'NOT_FOUND'},
                        'message': {'type': 'string', 'example': "The requested resource was not found."},
                        }
                    }
                }
            }
        }

        for code, description in error_codes.items():
            if code not in operation['responses']:
                operation['responses'][code] = {
                    'description': description,
                    'content': {
                        'application/json': {
                            'schema': error_schema_dict[code]
                        }
                    }
                }

    
    def _add_validation_error_responses(operation, path):
        '''Documents the standard error response structure across all operations.'''

        error_codes = {
            '400': 'Bad request -- validation error',
            '401': 'Authentication required',
            '403': 'Permission denied',
            '404': 'Not found',
        }

        error_schema_dict = {
            '400': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'VALIDATION_ERROR'},
                            'message': {'type': 'string', 'example': 'Validation failed'},
                            'fields': {
                                'type': 'object',
                                'description': 'Field-level validation errors',
                                'properties': {
                                    'fieldname': {'type': 'string', 'example': 'error_message'},
                                    'nested_fieldname': {
                                        'type': 'object',
                                        'properties': {
                                            'fieldname': {'type': 'string', 'example': 'error_message'},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '401': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'NOT_AUTHENTICATED'},
                            'message': {'type': 'string', 'example': "Authentication credentials were not provided."},
                        }
                    }
                }
            },
            '403': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'PERMISSION_DENIED'},
                        'message': {'type': 'string', 'example': "You do not have permission to perform this action."},
                        }
                    }
                }
            }, 
            '404': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'NOT_FOUND'},
                            'message': {'type': 'string', 'example': "The requested resource was not found."},
                        }
                    }
                }
            }
        }

        if '/appointments/' in path:
            error_codes['409'] = 'Appointment conflict'
            error_schema_dict['409'] = {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'APPOINTMENT_CONFLICT'},
                            'message': {'type': 'string', 'example': 'Time slot is already booked'},
                            'conflictWith': {
                                'type': 'object',
                                'properties': {
                                    'appointmentId': {'type': 'string', 'example': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                                    'patientName': {'type': 'string', 'example': 'Adel Imam'},
                                    'time': {'type': 'string', 'example': '11:00 - 12:30 PM'}
                                }
                            }
                        }
                    }
                }
            }
        
        elif '/whatsapp/' in path:
            error_codes['400'] = 'Invalid phone number'
            error_schema_dict['400'] = {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'example': 'INVALID_PHONE_NUMBER'},
                            'message': {'type': 'string', 'example': "Patient's phone number is invalid or not registered on WhatsApp."},
                        }
                    }
                }
            }
        for code, description in error_codes.items():
            if code not in operation['responses']:
                operation['responses'][code] = {
                    'description': description,
                    'content': {
                        'application/json': {
                            'schema': error_schema_dict[code]
                        }
                    }
                }


    def _extract_item_schema_from_reference(original_schema, result):
        """Extract the item schema from response reference"""
        
        if isinstance(original_schema, dict) and '$ref' in original_schema:
            ref_path = original_schema['$ref']
            
            #Extract schema name from #/components/schemas/PaginatedBaseUserList
            if ref_path.startswith('#/components/schemas/'):
                schema_name = ref_path.split('/')[-1]
                
                #Look up in components
                if ('components' in result and 
                    'schemas' in result['components'] and 
                    schema_name in result['components']['schemas']):
                    
                    resolved_schema = result['components']['schemas'][schema_name]
                    
                    #Extract the items schema from the paginated schema
                    if (isinstance(resolved_schema, dict) and 
                        'properties' in resolved_schema and
                        'results' in resolved_schema['properties'] and
                        'items' in resolved_schema['properties']['results']):
                        return resolved_schema['properties']['results']['items']
                    
        return original_schema


    def _get_category_from_path(path):
        for pattern, category in category_patterns.items():
            if pattern in path:
                return category
        return None
