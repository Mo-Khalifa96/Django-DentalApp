from utils.swagger_utils import (extend_schema, extend_schema_serializer, extend_schema_field,
                                extend_schema_view, OpenApiExample)


def get_message_history_schema():
    from services.serializers import MessagesHistorySerializer

    return extend_schema_view(
        get=extend_schema(
            tags=['WhatsApp'],
            responses={200: MessagesHistorySerializer},
            examples=[
                OpenApiExample(
                    name='Response',
                    response_only=True,
                    value={
                        "success": True,
                        "data": [
                            {
                                "messageId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "patientId": "3fa85f64-5717-4562-b3fc-2c963f66afb6",
                                "appointmentId": "3fa85f64-5717-4562-b3fc-2c963f66afc6",
                                "phone": "+20123456789",
                                "message": "text",
                                "type": "reminder",
                                "status": "delivered",
                                "failureReason": None,
                                "sentAt": "2026-08-27T23:22:07.987Z"
                            },
                            {
                                "messageId": "2fa85f64-5717-4562-b3fc-2c963f66afa1",
                                "patientId": "2fa85f64-5717-4562-b3fc-2c963f66afb1",
                                "appointmentId": "2fa85f64-5717-4562-b3fc-2c963f66afc1",
                                "phone": "+20123456789",
                                "message": "text 2",
                                "type": "reminder",
                                "status": "queued",
                                "failureReason": None,
                                "sentAt": "2026-08-26T11:00:05.907Z"
                            },
                        ],
                        "pagination": {
                            "pageSize": 5,
                            "hasNext": True,
                            "hasPrevious": False
                        },
                        "links": {
                            "next": "https://dtbackend.site/api/whatsapp/2fa85f64-5717-4562-b3fc-2c963f66afb1/?cursor=cD00ODY%3D",
                            "previous": None
                        },
                        "metadata": {
                            "userPermissions": {
                                "view.calendar": True,
                                "view.waitingRoom": True,
                                "view.patients": True,
                                "view.appointments": True,
                                "view.procedures": False,
                                "view.inventory": False,
                                "view.labs": False,
                                "view.labOrders": False,
                                "view.bills": False,
                                "view.transactions": True,
                                "view.invoices": False,
                                "view.insuranceProviders": False,
                                "view.doctorSchedules": True,
                                "view.sterilizationLogs": False,
                                "view.recalls": True,
                                "view.clinicalAnalytics": True,
                                "view.financialAnalytics": True,
                                "view.settings": True,
                                "send.whatsappMessage": True
                            }
                        }
                    }
                )
            ]
        )
    )

#Schema for patient whatsapp message history
message_history_schema = get_message_history_schema()