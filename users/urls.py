from django.urls import path
from users.views.users import (RetrieveUserProfileAPIView, ListCreateUserAPIView,
                              RetrieveUpdateDeleteUserAPIView, RetrieveUsersOptionsAPIView)
from users.views.auth import (TokenObtainPairView, TokenRefreshView, TokenVerifyView, 
                              TokenBlacklistView,  ChangePasswordAPIView, ResetEmailAPIView, 
                              ResetPasswordAPIView)
from users.views.doctor_schedules import (ListDoctorsSchedulesAPIView, CRUD_DoctorScheduleAPIView,
                                          CreateScheduleExceptionAPIView, DeleteScheduleExceptionAPIView,
                                          RetrieveDoctorSchedulesOptionsAPIView)


#url patterns
urlpatterns = [
    #JWT authentication urls
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),  
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'), 

    #Password change/reset urls
    path('auth/password-change/', ChangePasswordAPIView.as_view(), name='password_change'),
    path('auth/password-reset/', ResetEmailAPIView.as_view(), name='password_reset'),
    path('auth/password-reset/<uidb64>/<token>/', ResetPasswordAPIView.as_view(), name='password_reset_confirm'),
    
    #User profile url 
    path('auth/me/', RetrieveUserProfileAPIView.as_view(), name='view_user'),

    #User accounts urls
    path('users/', ListCreateUserAPIView.as_view(), name='list_create_users'),
    path('users/<uuid:id>/', RetrieveUpdateDeleteUserAPIView.as_view(), name='retrieve_update_delete_user'),
    path('users/options/', RetrieveUsersOptionsAPIView.as_view(), name='users_options'),

    #Doctor schedules urls
    path('doctor-schedules/', ListDoctorsSchedulesAPIView.as_view(), name='list_doctors_schedules'),
    path('doctor-schedules/<uuid:doctorId>/', CRUD_DoctorScheduleAPIView.as_view(
            http_method_names=['get', 'post', 'put', 'delete', 'options']
        ), name='CRUD_doctor_schedule'),
    path('doctor-schedule/<uuid:doctorId>/exceptions/', CreateScheduleExceptionAPIView.as_view(), name='create_schedule_exception'),
    path('doctor-schedule/<uuid:doctorId>/exceptions/<str:date>/', DeleteScheduleExceptionAPIView.as_view(), name='delete_schedule_exception'),
    path('doctor-schedules/options/', RetrieveDoctorSchedulesOptionsAPIView.as_view(), name='doctor_schedules_options'),
]
