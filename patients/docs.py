from utils.swagger_utils import (extend_schema, extend_schema_serializer, 
                                extend_schema_view, OpenApiExample)


def get_dentalchart_schema():
    '''Helper function for lazy import of dental chart schema to prevent circular import'''
    from patients.serializers.patients import DentalChartSerializer
    
    return extend_schema_view(
            get=extend_schema(
                tags=['Dental Chart'],
                responses={200: DentalChartSerializer},
                examples=[
                    OpenApiExample(
                        name='Response',
                        response_only=True,
                        description='''Response -- the full dental chart would include teeth numbers from 11 to 48 (FDI notation).<br><br>*Note:* you can find the valid status choices in "metadata."''',
                        value={
                            'success': True,
                            'data': {
                                'patientId': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                                'teeth': {
                                    "11": {
                                        "status": "healthy",
                                        "notes": ""
                                    },
                                    "12": {
                                        "status": "healthy",
                                        "notes": ""
                                    },
                                    "13": {
                                        "status": "cavity",
                                        "notes": ""
                                    },
                                    "n": {
                                        "status": "healthy",
                                        "notes": ""
                                    }
                                },
                                'lastUpdated': '2026-04-29T02:19:33.461755Z'
                            }
                        }
                    )
                ]
            ),
            patch=extend_schema(
                tags=['Dental Chart'],
                request=DentalChartSerializer,
                responses={200: DentalChartSerializer},
                examples=[
                    OpenApiExample(
                        name='Request body',
                        request_only=True,
                        description='Request body -- takes at least one tooth for update.',
                        value={
                            'teeth': {
                                "12": {
                                    "status": "filling",
                                    "notes": "Composite filling placed"
                                },
                                "32": {
                                    "status": "cavity",
                                    "notes": ""
                                },
                            },
                        },
                    ),
                    OpenApiExample(
                        name='Success Response (200 OK)',
                        response_only=True,
                        description='Response -- only updated teeth are returned.',
                        value={
                            'success': True,
                            'data': {
                                'patientId': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                                'teeth': {
                                "12": {
                                    "status": "filling",
                                    "notes": "Composite filling placed"
                                },
                                "32": {
                                    "status": "cavity",
                                    "notes": ""
                                },
                            },
                                'lastUpdated': '2026-04-29T02:19:33.461755Z'
                            }
                        }
                    ),
                    OpenApiExample(
                        name='Error Response (400 Bad request) - example 1',
                        response_only=True,
                        description='Error response with validation error.',
                        value={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Validation failed",
                                "fields": {
                                    "teeth": "Teeth data required for update."
                                }
                            }
                        }
                    ),
                    OpenApiExample(
                        name='Error Response (400 Bad request) - example 2',
                        response_only=True,
                        description='Error response with validation error.',
                        value={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Validation failed",
                                "fields": {
                                    "teeth": {
                                        "11": {
                                            "status": '"veneer" is not a valid choice.'
                                        }
                                    }
                                }
                            }
                        }
                    )
                ]
            ),
            put=extend_schema(
                tags=['Dental Chart'],
                request=DentalChartSerializer,
                responses={200: DentalChartSerializer},
                examples=[
                    OpenApiExample(
                        name='Request body',
                        request_only=True,
                        description='Request body -- takes full teeth dictionary {11 - 48}.',
                        value={
                            'teeth': {
                                "11": {
                                    "status": "healthy",
                                    "notes": ""
                                },
                                "12": {
                                    "status": "filling",
                                    "notes": "Composite filling placed"
                                },
                                "13": {
                                    "status": "cavity",
                                    "notes": ""
                                },
                                "n": {
                                    "status": "healthy",
                                    "notes": ""
                                }
                            },
                        },
                    ),
                    OpenApiExample(
                        name='Response',
                        response_only=True,
                        description='Response -- all teeth are returned.',
                        value={
                            'success': True,
                            'data': {
                                'patientId': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                                'teeth': {
                                    "11": {
                                        "status": "healthy",
                                        "notes": ""
                                    },
                                    "12": {
                                        "status": "filling",
                                        "notes": ""
                                    },
                                    "13": {
                                        "status": "cavity",
                                        "notes": ""
                                    },
                                    "n": {
                                        "status": "healthy",
                                        "notes": ""
                                    }
                                },
                                'lastUpdated': '2026-04-29T02:19:33.461755Z'
                            }
                        }
                    ),
                    OpenApiExample(
                        name='Error Response (400 Bad request) - example 1',
                        response_only=True,
                        description='Error response with validation error.',
                        value={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Validation failed",
                                "fields": {
                                    "teeth": "Teeth data required for update."
                                }
                            }
                        }
                    ),
                    OpenApiExample(
                        name='Error Response (400 Bad request) - example 2',
                        response_only=True,
                        description='Error response with validation error.',
                        value={
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Validation failed",
                                "fields": {
                                    "teeth": {
                                        "11": {
                                            "status": '"veneer" is not a valid choice.'
                                        }
                                    }
                                }
                            }
                        }
                    )
                ]
            )
        )


#Schema for create patient serializer
create_patient_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Request body',
            request_only=True,
            value={
                "name": "John Smith",
                "age": 25,
                "gender": "Male",
                "countryCode": "+966",
                "phone": "123456789",
                "email": "johnsmith@example.com",
                "address": "Maadi, Cairo",
                "nationalId": "525400222211111",
                "bloodType": "A+",
                "allergies": ['Latex', 'Pencillin'], 
                "insurance": '', 
                "insuranceId": '', 
                "notes": '',
                "branchId": 'ebe27408-2fb9-42b2-977a-fbaa1bf0a396'
            }
        ), 
        OpenApiExample(
            name='Success Response (201 CREATED)', 
            response_only=True,
            #status_codes=[201],
            value={
                'success': True, 
                'data': {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "name": "John Smith",
                    "age": 25,
                    "gender": "Male",
                    "countryCode": "+966",
                    "phone": "123456789",
                    "email": "johnsmith@example.com",
                    "address": "",
                    "nationalId": "525400222211111",
                    "bloodType": "A+",
                    "allergies": ['Latex', 'Pencillin'], 
                    "insurance": '', 
                    "insuranceId": '', 
                    "notes": "",
                    "branchId": 'ebe27408-2fb9-42b2-977a-fbaa1bf0a396',
                    "createdAt": "2026-04-24T23:33:54.610Z",
                    "updatedAt": "2026-04-24T23:33:54.610Z"
                }
            }
        ),
        OpenApiExample(
            name='Error Response (400 Bad Request)',
            response_only=True,
            #status_codes=[400],
            value={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "fields": {
                            "phone": "Phone number is invalid. Please enter a valid number."
                        }
                    }
            }
        ),
    ]
)

#Schema for update patient serializer
update_patient_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Request body',
            request_only=True,
            value={
                'countryCode': '0010',
                'phone': '0123456789', 
                'address': 'Maadi, Cairo',
                "nationalId": "525400222211100",
                'bloodType': 'A+', 
                'allergies': ['Latex'], 
                'insurance': '', 
                'insuranceId': '', 
                'notes': ''
            }
        ), 
        OpenApiExample(
            name='Success Response (200 OK)', 
            response_only=True,
            value={
                'success': True, 
                'data': {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "name": "John Smith",
                    'countryCode': '0010',
                    'phone': '0123456789', 
                    'address': 'Maadi, Cairo',
                    "nationalId": "525400222211100",
                    'bloodType': 'A+', 
                    'allergies': ['Latex'], 
                    'insurance': '', 
                    'insuranceId': '', 
                    'notes': '',
                    "updatedAt": "2026-04-24T17:32:03.201Z"
                }
            }
        ),
        OpenApiExample(
            name='Error Response (400 Bad Request)',
            response_only=True,
            value={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "fields": {
                            "phone": "Phone number is invalid."
                        }
                    }
            }
        ),
    ]
)

#Schema for patients options serializer 
patients_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'genderChoices': [
                    {'value': 'male', 'label': 'Male'},
                    {'value': 'female', 'label': 'Female'},
                ],
                'statusChoices': [
                    {'value': 'active', 'label': 'active'},
                    {'value': 'inactive', 'label': 'inactive'},
                ],
                'bloodTypeChoices': [
                    {'value': 'A+', 'label': 'A+'},
                    {'value': 'A-', 'label': 'A-'},
                    {'value': 'B+', 'label': 'B+'},
                    {'value': 'B-', 'label': 'B-'},
                    {'value': 'O+', 'label': 'O+'},
                    {'value': 'O-', 'label': 'O-'},
                    {'value': 'AB+', 'label': 'AB+'},
                    {'value': 'AB-', 'label': 'AB-'},
                ],
            }
        )
    ]

) 

#Schema for patients options serializer 
dentalchart_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                "toothNumberChoices": [
                    {"value": "11", "label": "11"},
                    {"value": "12", "label": "12"},
                    {"value": "13", "label": "13"},
                    {"value": "n", "label": "n"},
                    {"value": "48", "label": "48"},
                ],
                'toothStatusChoices': [
                    {'value': 'healthy', 'label': 'healthy'},
                    {'value': 'cavity', 'label': 'cavity'},
                    {'value': 'filling', 'label': 'filling'},
                    {'value': 'crown', 'label': 'crown'},
                    {'value': 'root canal', 'label': 'root canal'},
                    {'value': 'extraction required', 'label': 'extraction required'},
                    {'value': 'implant', 'label': 'implant'},
                    {'value': 'missing', 'label': 'missing'},
                    {'value': 'cracked', 'label': 'cracked'}
                ],
            }
        )
    ]

) 


#Schema for procedure options serializer 
visit_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description="'optionalProcedureChoices' provides ready-made procedure options for the 'procedures' list.<br>'optionalProcedureTypeChoices' provides value/label options for procedure categories.",
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'visitTypeChoices': [
                    {'value': 'routine_checkup', 'label': 'Routine Checkup'},
                    {'value': 'follow_up', 'label': 'Follow up'},
                    {'value': 'emergency', 'label': 'Emergency'}
                ],
                'optionalProcedureChoices': [
                    {
                    'name': 'Routine Examination',
                    'category': 'Routine Checkup',
                    'duration': 30,
                    'price': '$200.00',
                    },
                    {
                    'name': 'Composite Filling',
                    'category': 'Restorative',
                    'duration': 45,
                    'price': '$450.00',
                    },
                ],
                'optionalProcedureTypeChoices': [
                    {'value': 'routine_checkup', 'label': 'Routine Checkup'},
                    {'value': 'cosmetic', 'label': 'Cosmetic'},
                    {'value': 'diagnostic', 'label': 'Diagnostic'},
                    {'value': 'endodontic', 'label': 'Endodontic'},
                    {'value': 'implant', 'label': 'Implant'},
                    {'value': 'preventive', 'label': 'Preventive'},
                    {'value': 'prosthetic', 'label': 'Prosthetic'},
                    {'value': 'restorative', 'label': 'Restorative'},
                    {'value': 'surgical', 'label': 'Surgical'},
                ],
            }
        )
    ]

) 


#Schema for cancel appointment serializer
cancel_appointment_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Request body',
            request_only=True,
            value={
                'reason': 'Patient cancelled due to emergency.'
                }
        ),
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'success': True, 
                'data': {
                    'success': True, 
                    'message': 'Appointment cancelled successfully.'
                }
            }
        ),
    ]
)

#Schema for procedure options serializer 
appointments_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                "patientChoices": [
                    {"patientId": "41f1c0fd-3b69-4289-9a8a-83eb205702c3", "name": "Sherif Zatona"},
                    {"patientId": "ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4", "name": "Nelly Karim"},
                    {"patientId": "5dc6201a-3ef7-4434-a108-223f5c8d3ba1", "name": "Saed Ashraf"}
                ],
                "doctorChoices": [
                    {"doctorId": "8d9e0abc-7abb-4497-a2ed-19737c92a229", "name": "Layla Hassan"},
                    {"doctorId": "ec4ebe94-c8a6-45d5-8cc6-675cef7bbafe", "name": "Ahmed Hassan"}, 
                    {"doctorId": "0078af5e-7b68-4c29-9c81-04c8665fee68", "name": "Ghassan Mattar"}
                ],
                "typeChoices": [
                    {"value": "routine_checkup", "label": "Routine Checkup"},
                    {"value": "follow_up", "label": "Follow up"},
                    {"value": "emergency", "label": "Emergency"}
                ],
                "statusChoices": [
                    {"value": "pending", "label": "pending"},
                    {"value": "confirmed", "label": "confirmed"},
                    {"value": "completed", "label": "completed"},
                    {"value": "cancelled", "label": "cancelled"}
                ],
                "roomChoices": [
                    {"value": "Chair 1", "label": "Chair 1"},
                    {"value": "Chair 2", "label": "Chair 2"},
                    {"value": "Consultation Room", "label": "Consultation Room"}
                ]
            }
        )
    ]

) 


#Schema for treatment plans options serializer 
treatmentplans_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'installmentOptions': [
                    {'value': 1, 'label': 'Full payment'},
                    {'value': 3, 'label': '3 months'},
                    {'value': 6, 'label': '6 months'},
                    {'value': 12, 'label': '12 months'},
                ],
                'treatmentStatusChoices': [
                    {'value': 'active', 'label': 'active'},
                    {'value': 'completed', 'label': 'completed'},
                    {'value': 'cancelled', 'label': 'cancelled'},
                ],
                "procedureChoices": [
                    {"procedureId": "373b6f45-a50b-496b-90bd-814cae5ed93d", "name": "Dental Implant"}, 
                    {"procedureId": "0994c96a-92fa-4451-b6e0-045c91ff050f", "name": "Dental Bridge (3-unit)"}, 
                    {"procedureId": "ed87388f-3037-47e1-86ea-b78a5d37e115", "name": "Dental Crown (Ceramic)"}
                ],
                'itemStatusChoices': [
                    {'value': 'pending', 'label': 'pending'},
                    {'value': 'in_progress', 'label': 'in progress'},
                    {'value': 'completed', 'label': 'completed'},
                ],
                "validToothNumbers": [
                    {"value": "11", "label": "11"},
                    {"value": "12", "label": "12"},
                    {"value": "13", "label": "13"},
                    {"value": "n", "label": "n"},
                    {"value": "85", "label": "85"},
                ],
            }
        )
    ]
) 


#Schema for patient recalls options serializer
patient_recalls_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description=(
                f'Assign `branchId` to filter patient choices by branch ',
                f'and assign `doctorId` to filter patient choices by `dentist` user.\n',
                f'Empty query parameters return all choices across the system.'
            ),
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                "patientChoices": [
                    {"patientId": "41f1c0fd-3b69-4289-9a8a-83eb205702c3", "name": "Sherif Zatona", "phone": "+20123456789"},
                    {"patientId": "ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4", "name": "Nelly Karim", "phone": "+2011120392093"},
                    {"patientId": "5dc6201a-3ef7-4434-a108-223f5c8d3ba1", "name": "Ahmed El-Saka", "phone": "011"}
                ],
                "recallTypeChoices": [
                    {"value": 'checkup', "label": 'Checkup'},
                    {"value": 'post_procedure', "label": 'Post-procedure'},
                    {"value": 'treatment', "label": 'Treatment'},
                    {"value": 'custom', "label": 'Custom'}
                ],
                "recallStatusChoices": [
                    {"value": 'pending', "label": 'Pending'},
                    {"value": 'contacted', "label": 'Contacted'},
                    {"value": 'confirmed', "label": 'Confirmed'},
                    {"value": 'no_answer', "label": 'No answer'},
                    {"value": 'declined', "label": 'Declined'}
                ]
            }
        )
    ]
)

