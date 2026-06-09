from utils.swagger_utils import (extend_schema, extend_schema_serializer, extend_schema_field,
                                extend_schema_view, OpenApiExample)



#List bills schema 
list_bills_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            description='Response without snapshot fields for non-admin users.',
            response_only=True,
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                        'visitIds': [
                            'c3d4e5f6-3456-7890-cdef-3456789012cd',
                            'd4e5f6a7-4567-8901-defa-4567890123de',
                        ],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'description': 'Full mouth rehabilitation - Session 1',
                        'discount': '150.00',
                        'subtotal': '2350.00',
                        'total': '2200.00',
                        'currency': 'USD',
                        'status': 'partial',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'updatedAt': '2026-05-01T10:15:30.000Z',
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': None,
                        'visitIds': [
                            'e5f6a7b8-5678-9012-efab-5678901234ef',
                        ],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'description': 'Routine checkup and scaling',
                        'discount': '0.00',
                        'subtotal': '300.00',
                        'total': '300.00',
                        'currency': 'USD',
                        'status': 'unpaid',
                        'createdAt': '2026-05-01T09:00:00.000Z',
                        'updatedAt': '2026-05-01T09:00:00.000Z',
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                "links": {
                    'next': 'api/bills/?page=3',
                    'previous': 'api/bills/?page=1'
                },
                'metadata': {
                    'userPermissions': {
                        'view.calender': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.preferences': True,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes additional details, snapshot fields, and isDeleted flag.',
            value={
                'success': True,
                'data': [
                    {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                        'treatmentTitle': 'Full Mouth Rehabilitation',
                        'visitIds': [
                            'c3d4e5f6-3456-7890-cdef-3456789012cd',
                            'd4e5f6a7-4567-8901-defa-4567890123de',
                        ],
                        'procedures': ['Root Canal Treatment', 'Dental Crown (Ceramic)'],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'description': 'Full mouth rehabilitation - Session 1',
                        'discount': '150.00',
                        'subtotal': '2350.00',
                        'total': '2200.00',
                        'currency': 'USD',
                        'status': 'partial',
                        'createdBy': 'Dr. Layla Hassan',
                        'createdAt': '2026-04-24T23:33:54.610Z',
                        'updatedAt': '2026-05-01T10:15:30.000Z',
                        'isDeleted': False,
                    },
                    {
                        'id': '4gb96g75-6828-5673-c4gd-3d4f66bgb7g7',
                        'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                        'patientName': 'Ahmed Khaled',
                        'treatmentId': None,
                        'treatmentTitle': None,
                        'visitIds': [
                            'e5f6a7b8-5678-9012-efab-5678901234ef',
                        ],
                        'procedures': [],
                        'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                        'branchName': 'Main Branch',
                        'description': 'Routine checkup and scaling',
                        'discount': '0.00',
                        'subtotal': '300.00',
                        'total': '300.00',
                        'currency': 'USD',
                        'status': 'unpaid',
                        'createdBy': 'Dr. Layla Hassan',
                        'createdAt': '2026-05-01T09:00:00.000Z',
                        'updatedAt': '2026-05-01T09:00:00.000Z',
                        'isDeleted': False,
                    },
                ],
                'pagination': {
                    'page': 2,
                    'limit': 25,  #TODO
                    'total': 120,
                    'totalPages': 5,
                    'hasNext': True, 
                    'hasPrev': False,
                },
                "links": {
                    'next': 'api/bills/?page=3',
                    'previous': 'api/bills/?page=1'
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
                        'view.transactions': False,
                        'view.invoices': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': True,
                        'view.preferences': True,
                        'create.bill': True,
                        'update.bill': True,
                        'delete.bill': True
                    }
                }
            }
        ),
    ]
)

    
#Retrieve bills schema
retrieve_bills_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Non-Admin Response',
            response_only=True,
            description='Response without snapshot fields for non-admin users.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                    'visitIds': [
                        'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'd4e5f6a7-4567-8901-defa-4567890123de',
                    ],
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'description': 'Full mouth rehabilitation - Session 1',
                    'discount': '150.00',
                    'subtotal': '2350.00',
                    'total': '2200.00',
                    'currency': 'USD',
                    'status': 'partial',
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'updatedAt': '2026-05-01T10:15:30.000Z',
                },
                'metadata': {
                    'userPermissions': {
                        'view.calender': True,
                        'view.waitingRoom': True,
                        'view.patients': True,
                        'view.appointments': True,
                        'view.procedures': True,
                        'view.inventory': True,
                        'view.labs': False,
                        'view.labOrders': True,
                        'view.bills': False,
                        'view.transactions': False,
                        'view.invoices': False,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': False,
                        'view.preferences': True,
                        'create.bill': True,
                        'update.bill': False,
                        'delete.bill': False
                    }
                }
            }
        ),
        OpenApiExample(
            name='Admin Response',
            response_only=True,
            description='Admin response includes snapshot fields, procedures, and isDeleted flag.',
            value={
                'success': True,
                'data': {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
                    'patientName': 'Ahmed Khaled',
                    'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
                    'treatmentTitle': 'Full Mouth Rehabilitation',
                    'visitIds': [
                        'c3d4e5f6-3456-7890-cdef-3456789012cd',
                        'd4e5f6a7-4567-8901-defa-4567890123de',
                    ],
                    'procedures': ['Root Canal Treatment', 'Dental Crown (Ceramic)'],
                    'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
                    'branchName': 'Main Branch',
                    'description': 'Full mouth rehabilitation - Session 1',
                    'discount': '150.00',
                    'subtotal': '2350.00',
                    'total': '2200.00',
                    'currency': 'USD',
                    'status': 'partial',
                    'createdBy': 'Dr. Layla Hassan',
                    'createdAt': '2026-04-24T23:33:54.610Z',
                    'updatedAt': '2026-05-01T10:15:30.000Z',
                    'isDeleted': False,
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
                        'view.transactions': False,
                        'view.invoices': True,
                        'view.doctorSchedules': True,
                        'view.sterilizationLogs': True,
                        'view.recalls': True,
                        'view.clinicalAnalytics': True,
                        'view.financialAnalytics': False,
                        'view.settings': True,
                        'view.preferences': True,
                        'create.bill': True,
                        'update.bill': True,
                        'delete.bill': True
                    }
                }
            }
        ),
    ]
)


        # OpenApiExample(
        #     name='Create Bill Request',
        #     request_only=True,
        #     description='Payload for creating a new bill.',
        #     value={
        #         'patientId': 'a1b2c3d4-1234-5678-abcd-1234567890ab',
        #         'treatmentId': 'b2c3d4e5-2345-6789-bcde-2345678901bc',
        #         'visitIds': [
        #             'c3d4e5f6-3456-7890-cdef-3456789012cd',
        #         ],
        #         'branchId': 'e5f6a7b8-5678-9012-efab-5678901234ef',
        #         'description': 'Full mouth rehabilitation - Session 1',
        #         'discount': '150.00',
        #         'subtotal': '2350.00',
        #         'total': '2200.00',
        #         'currency': 'USD',
        #     }
        # ),



#Schema for clinic tax config options serializer
# tax_config_options_schema = extend_schema_serializer(
#     examples=[
#         OpenApiExample(
#             name='Response',
#             response_only=True,
#             value={
#                 'branchChoices': [
#                     {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
#                     {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
#                 ],
#             }
#         )
#     ]
# )


#Schema for bills options serializer
bills_options_schema = extend_schema_serializer(
    examples=[
        OpenApiExample(
            name='Response',
            description=(
                f'Assign `branchId` to filter patient choices by branch, ',
                f'assign `doctorId` to filter patient choices by `dentist` user, ',
                f'and assign `patientId` to filter treatment and visit choices by patient.\n',
                f'Empty query parameters return all choices across the system.'
            ),
            response_only=True,
            value={
                'branchChoices': [
                    {'branchId': '9ca1d622-94af-4ea5-b87a-bf9f6611d6ab', 'name': 'Main Branch'},
                    {'branchId': '8ef5c0eb-ab95-4d13-a1b4-04f634534587', 'name': 'Heliopolis Branch'},
                ],
                'patientChoices': [
                    {'patientId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3', 'name': 'Ahmed Khaled'},
                    {'patientId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4', 'name': 'Khaled Ahmed'},
                ],
                'patientTreatmentChoices': [
                    {'treatmentId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                    {'treatmentId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4'},
                ],
                'patientVisitChoices': [
                    {'visitId': '41f1c0fd-3b69-4289-9a8a-83eb205702c3'},
                    {'visitId': 'ea0b1f0f-df7e-4a0a-9bb6-67ecfa1ecef4'},
                ],
            }
        )
    ]
) 
