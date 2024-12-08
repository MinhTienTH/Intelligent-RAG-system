# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('check_account/', views.check_account, name='check_account'),
    path('check_email/', views.check_email, name='check_email'),
    path('chat/', views.chat_response, name='chat_response'),
    path('login_auth/', views.login_auth, name='login_auth'),
    path('signupviews/', views.signup_views, name='signupviews'),
    path('verifyOtp/', views.check_otp, name='verifyOtp'),
    path('reset_password/', views.reset_password_view, name='reset_password_view'),
    path('reset_password/submit/', views.reset_password, name='reset_password_submit'),
    #path('SendMessage', views.response_user, name='SendMessage'), 
    #path('', views.generate_chat, name='chat'),
    #path('load-documents/', views.load_documents_view, name='load_documents')
]