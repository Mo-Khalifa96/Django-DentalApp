from utils.swagger_utils import (extend_schema, extend_schema_serializer, 
                                extend_schema_view, OpenApiExample)


#Schema for dashboard statistics 
dashboard_stats_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response (200 OK) -- full access',
            description=(
                'Returns full statistics for the dashboard for Admin users and users with permission to view financial analytics.\n'
                'Without date parameters, defaults to current-day / current-week / current-month windows.\n'
                'Providing `dateRange` overrides the relevant aggregations to the specified range.\n\n'
            ),
            response_only=True,
            value={
                'success': True, 
                'data': {
                    'patientsTotal': 340,
                    'patientsNew': 12,
                    'appointmentsCount': 18,
                    'appointmentsCompleted': 11,
                    'revenue': 47500.00,
                    'outstanding': 8200.00,
                    # 'currency': 'SAR',
                },
                'metadata': {
                    'userPermissions': {
                        'view.calender': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': True,
                        'view.transactions': True,
                        'view.invoices': True,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': True,
                        'view.settings': True
                    }
                }
            }
        ),
        OpenApiExample(
            name='Response (200 OK) -- no financial analytics',
            description=(
                'Returns statistics for the dashboard without financial analytics fields for users without the financial analytics permission.\n'
                'Without date parameters, defaults to current-day / current-week / current-month windows.\n'
                'Providing `dateRange` overrides the relevant aggregations to the specified range.\n\n'
            ),
            response_only=True,
            value={
                'success': True, 
                'data': {
                    'patientsTotal': 340,
                    'patientsNew': 12,
                    'appointmentsCount': 18,
                    'appointmentsCompleted': 11,
                },
                'metadata': {
                    'userPermissions': {
                        'view.calender': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': False,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': False,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': True
                    }
                }
            }
        ),
        OpenApiExample(
            name='Response (200 OK) -- no analytics',
            description=(
                'Returns nothing for users without neither clinical nor financial analytics permission.\n'
            ),
            response_only=True,
            value={
                'success': True, 
                'data': {
                    'patientsTotal': None,
                    'patientsNew': None,
                    'appointmentsCount': None,
                    'appointmentsCompleted': None,
                },
                'metadata': {
                    'userPermissions': {
                        'view.calender': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': False,
                        'view.inventory': True,
                        'view.labs': True,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.insuranceProviders': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': False,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': True
                    }
                }
            }
        ),
        OpenApiExample(
            name='Error Response (400 Bad Request) -- example 1',
            description='Validation error: Invalid branch id.',
            response_only=True,
            value={
                'success': False,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Branch does not exist.',
                }
            }
        ),
        OpenApiExample(
            name='Error Response (400 Bad Request) -- example 2',
            description='Validation error: Invalid date range.',
            response_only=True,
            value={
                'success': False,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalide date range query. Expected: [today, week, month].',
                }
            }
        )
    ]
)

#Schema for dashboard options 
dashboard_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'}, 
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'doctorChoices': [
                    {'doctorId': '8d9e0abc-7abb-4497-a2ed-19737c92a229', 'doctorName': 'Layla Hassan'},
                    {'doctorId': 'ec4ebe94-c8a6-45d5-8cc6-675cef7bbafe', 'doctorName': 'Ahmed Hassan'}, 
                    {'doctorId': '0078af5e-7b68-4c29-9c81-04c8665fee68', 'doctorName': 'Ghassan Mattar'}
                ],
            }
        )
    ]
)


#Schema for branch choices 
branch_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'weekDaysChoices': [
                    {'value': 0, 'label': 'Sunday'},
                    {'value': 1, 'label': 'Monday'},
                    {'value': 2, 'label': 'Tuesday'},
                    {'value': 3, 'label': 'Wednesday'},
                    {'value': 4, 'label': 'Thursday'},
                    {'value': 5, 'label': 'Friday'},
                    {'value': 6, 'label': 'Saturday'},
                ]
            }
        )
    ]
)


#Schema for procedures choices
procedures_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'categoryChoices': [
                    {'value': 'routine_checkup', 'label': 'Routine Checkup'},
                    {'value': 'cosmetic', 'label': 'Cosmetic'},
                    {'value': 'diagnostic', 'label': 'Diagnostic'},
                    {'value': 'endodontic', 'label': 'Endodontic'},
                    {'value': 'implant', 'label': 'Implant'},
                    {'value': 'preventive', 'label': 'Preventive'},
                    {'value': 'prosthetic', 'label': 'Prosthetic'},
                    {'value': 'restorative', 'label': 'Restorative'},
                    {'value': 'surgical', 'label': 'Surgical'},
                ]
            }
        )
    ]
)


#Schema for inventory category choices
inventory_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'categoryChoices': [
                    {'value': 'Anesthetics', 'label': 'Anesthetics'},
                    {'value': 'Medicine', 'label': 'Medicine'},
                    {'value': 'Needles', 'label': 'Needles'},
                ],
                'unitChoices': [
                    {'value': 'boxes', 'label': 'boxes'},
                    {'value': 'liters', 'label': 'liters'},
                ]
            }
        )
    ]
)


#Schema for waiting room options serializer 
waiting_room_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'doctorChoices': [
                    {'doctorId': '8d9e0abc-7abb-4497-a2ed-19737c92a229', 'doctorName': 'Layla Hassan'},
                    {'doctorId': 'ec4ebe94-c8a6-45d5-8cc6-675cef7bbafe', 'doctorName': 'Ahmed Hassan'}, 
                    {'doctorId': '0078af5e-7b68-4c29-9c81-04c8665fee68', 'doctorName': 'Ghassan Mattar'}
                ],
                'statusChoices': [
                    {'value': 'waiting', 'label': 'Waiting'},
                    {'value': 'in_chair', 'label': 'In chair'},
                    {'value': 'done', 'label': 'Done'},
                ],
                'roomChoices': [
                    {'value': 'Chair 1', 'label': 'Chair 1'},
                    {'value': 'Chair 2', 'label': 'Chair 2'},
                    {'value': 'Consultation Room', 'label': 'Consultation Room'},
                ]
            }
        )
    ]
)


#Schema for labs and lab orders options
labs_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'labChoices': [
                    {'labId': '373b6f45-a50b-496b-90bd-814cae5ed93d', 'name': 'Heliopolis Dental Lab '}, 
                    {'labId': '0994c96a-92fa-4451-b6e0-045c91ff050f', 'name': 'Dental Technologies Lab'}, 
                ],
                'patientChoices': [
                    {'patientId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3', 'name': 'Ahmed Khaled'},
                    {'patientId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4', 'name': 'Khaled Ahmed'},
                ],
                'procedureChoices': [
                    {'procedureId': '373b6f45-a50b-496b-90bd-814cae5ed93d', 'name': 'Dental Implant'}, 
                    {'procedureId': 'ed87388f-3037-47e1-86ea-b78a5d37e115', 'name': 'Dental Crown (Ceramic)'}
                ],
                'orderStatus': [
                    {'value': 'sent', 'label': 'Sent'},
                    {'value': 'in_production', 'label': 'In production'},
                    {'value': 'delivered', 'label': 'Delivered'},
                    {'value': 'received', 'label': 'Received'},
                ],
                'validToothNumbers': [
                    {'value': '11', 'label': '11'},
                    {'value': '12', 'label': '12'},
                    {'value': '13', 'label': '13'},
                    {'value': 'n', 'label': 'n'},
                    {'value': '85', 'label': '85'},
                ],
            }
        )
    ]
) 


#Schema for sterilization logs options
sterilization_logs_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'cycleTypeChoices': [
                    {'value': 'pre_vacuum', 'label': 'Pre-vacuum'},
                    {'value': 'gravity', 'label': 'Gravity'},
                    {'value': 'flash_immediate', 'label': 'Flash/Immediate'},
                    {'value': 'chemical_vapor', 'label': 'CHemical Vapor'},
                    {'value': 'dry_heat', 'label': 'Dry Heat'},
                ],
                'instrumentSetsChoices': [
                    {'value': 'basic_exam_kit', 'label': 'Basic Exam Kit'},
                    {'value': 'extraction_kit', 'label': 'Extraction Kit'},
                    {'value': 'rct_kit', 'label': 'RCT Kit'},
                    {'value': 'implant_kit', 'label': 'Implant Kit'},
                    {'value': 'perio_kit', 'label': 'Perio Kit'},
                    {'value': 'ortho_kit', 'label': 'Ortho Kit'},
                    {'value': 'surgical_kit', 'label': 'Surgical Kit'},
                    {'value': 'handpieces', 'label': 'Handpieces'},
                    {'value': 'impression_trays', 'label': 'Impression Trays'},
                    {'value': 'other', 'label': 'Other'},
                ],
                'resultChoices': [
                    {'value': 'passed', 'label': 'Passed'},
                    {'value': 'failed', 'label': 'Failed'},
                ]
            }
        )
    ]
)

