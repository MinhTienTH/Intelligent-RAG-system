# views.py
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib.auth import authenticate, login

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt

from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv
from huggingface_hub import login
from langchain_community.llms import Ollama
from langchain_community.vectorstores import DocArrayInMemorySearch
from langchain_core.output_parsers import StrOutputParser
from langchain_openai.embeddings import OpenAIEmbeddings
import random
from django.core.mail import send_mail
from django.conf import settings
from langchain.prompts import PromptTemplate
from operator import itemgetter
import json
import re
import sys
import os
import logging
import torch

load_dotenv()

OPENAI_KEY_api = os.getenv("OPENAI_API_KEY")
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_time_based_greeting(hour):
    """
    Generate a time-based greeting based on the current hour.
    
    Args:
        hour (int): Hour of the day (0-23)
    
    Returns:
        str: Appropriate greeting for the time of day
    """
    if hour < 12:
        return "Good Morning"
    elif 12 <= hour < 18:
        return "Good Afternoon"
    elif 18 <= hour < 21:
        return "Good Evening"
    else:
        return "Good Night"

@csrf_exempt
def index_view(request):
    logger.info(f"Received request from {request.META.get('REMOTE_ADDR')} for index view.")
    try:
        response = render(request, "index.html")
        logger.info("Successfully rendered index.html")
        return response
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        return JsonResponse({'error': 'Internal Server Error'}, status=500)

historical_messages = []
first_response = True

@csrf_exempt
def chat_response(request):

    global historical_messages, first_response
    
    """
    Handle chat messages and generate AI responses.
    
    Args:
        request (HttpRequest): Incoming HTTP request
    
    Returns:
        JsonResponse: AI-generated response or error message
    """
    # Parse the incoming JSON data
    data = json.loads(request.body)
    user_message = data.get('question', '').strip()
    
    logger.info(f"Received message: {user_message}")

    historical_messages.append(f"User: {user_message}")
    combined_context = "\n".join(historical_messages[-5:])
    
    model = Ollama(model="llama3.2:1b")
    
    if first_response:
        current_time = datetime.now()
        greeting = get_time_based_greeting(current_time.hour)
        template = f"In your first response, please give me a greeting based on the time {greeting}, and after that, you need to answer my question correctly: {user_message}, and whenever I ask you to remember something in the past, please look at my historical conversation context:{combined_context},"
        first_response=False
    else:
        template = f"Please answer my question correctly: {user_message} and do not need to greeting me again, and whenever I ask you to remember something in the past, please look at my historical conversation context:{combined_context}"


    # Modify system prompt to include greetingmodel = Ollama(model="llama3.2:1b")
    prompt = PromptTemplate(input_variables=["user_message"], template=template)

    chain = prompt | model
    
    # Call OpenAI API to generate a response
    
    bot_response = chain.invoke({"user_message":user_message})
    
    historical_messages.append(f"AI: {bot_response}")

    # Return JSON response
    return JsonResponse({
        'response': bot_response,
        'status': 'success'
    })

def login_view(request):
    return render(request, 'login.html')

# Configure logging
logger = logging.getLogger(__name__)

def login_auth(request):
    if request.method == "POST":
        try:
            # Log the entire request details for debugging
            logger.info(f"Request method: {request.method}")
        
            # Attempt to parse request body
            data = json.loads(request.body)
            logger.info(f"Parsed request data: {data}")

            # Extract login credentials
            account = data.get('account', '').strip()
            password = data.get('password', '').strip()

            # Validate inputs
            if not account or not password:
                return JsonResponse({'status': 'error', 'message': 'Identifier and password are required'}, status=400)

            # Determine login method
            user = User.objects.filter(username=account).first()
            
            if user is None:
                return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)

            auth_user = authenticate(username=user.username, password=password)
            
            if auth_user is not None:
                #login(request, auth_user)
                logger.info(f"User {auth_user.username} logged in successfully.")
                return JsonResponse({'status': 'success', 'redirect': '/'})  # Optionally redirect after login
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid credentials'}, status=401)

        except json.JSONDecodeError:
            logger.error("Invalid JSON data received")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in login_auth: {e}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
def check_account(request):
    if request.method == 'GET':
        account = request.GET.get('account', '').strip()
        
        # Add more validation for username
        if not account:
            return JsonResponse({'exists': False, 'error': 'Username cannot be empty'})
        
        # Optional: Add username format validation
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', account):
            return JsonResponse({'exists': False, 'error': 'Invalid username format'})
        
        exists = User.objects.filter(username=account).exists()
        return JsonResponse({'exists': exists})

@csrf_exempt
def check_email(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        request.session['reset_email'] = email
        # Check if the email exists in your database
        user_exists = User.objects.filter(email=email).exists()

        if user_exists:
            otp = send_otp(request, email)  # Call the function to send the OTP
            if otp is not None:
                return JsonResponse({'exists': 'true', 'message': 'OTP sent to your email!'})
            else:
                return JsonResponse({'exists': 'false', 'error': 'Failed to send OTP. Please try again.'})
        else:
            return JsonResponse({'exists': 'false', 'error': 'Email not registered.'})

    return JsonResponse({'exists': 'false', 'error': 'Invalid request method'})

def check_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        otp_generated = data.get('otp', '').strip()  # Get the OTP from the request
        otp_stored = request.session.get('otp')  # Retrieve the stored OTP from the session

        print(f"Generated OTP: {otp_generated}")  # Print the OTP received from the user
        print(f"Stored OTP: {otp_stored}")  # Print the OTP stored in the session

        if otp_generated == otp_stored:  # Use '==' for comparison
            return JsonResponse({
                "otp_generated": otp_generated,
                "otp_stored": otp_stored,
                'exists': "OK",
                'message': 'OTP verified successfully!'
            })
        else:
            return JsonResponse({
                "otp_generated": otp_generated,
                "otp_stored": otp_stored,
                'exists': False,
                'error': 'Invalid OTP. Please try again.'
            })

    return JsonResponse({'exists': False, 'error': 'Invalid request method'})

def signup(request):

    return render(request, "signup.html")

def forgot_password(request):
    return render(request, "forgot_password.html")

@csrf_exempt
def signup_views(request):
    ##print(request.META, flush=True) 
    if request.method == 'POST':
        try:
            # Parse JSON data
            logger.info(f"Raw request body: {request.body.decode('utf-8')}")

            data = json.loads(request.body)
            logger.info(f"Received data: {data}")

            # Extract user details
            account = data.get('account', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()
            full_name = data.get('fullname', '').strip()

            # Comprehensive validation
            errors = {}

            # Username validation
            if not account:
                errors['account'] = 'Username is required'
            elif not re.match(r'^[a-zA-Z0-9_]{3,20}$', account):
                errors['account'] = 'Username must be 3-20 characters, alphanumeric or underscore'
            elif User.objects.filter(username=account).exists():
                errors['account'] = 'This account is already taken'

            # Email validation
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not email:
                errors['email'] = 'Email is required'
            elif not re.match(email_regex, email):
                errors['email'] = 'Invalid email format'
            elif User.objects.filter(email=email).exists():
                errors['email'] = 'This email is already registered'

            # Password validation
            if not password:
                errors['password'] = 'Password is required'
            elif len(password) < 8:
                errors['password'] = 'Password must be at least 8 characters long'

            # Full name validation
            if not full_name:
                errors['fullname'] = 'Full name is required'
            elif len(full_name) < 2:
                errors['fullname'] = 'Full name is too short'

            # If there are any errors, return them
            if errors:
                logger.info(f"Validation errors: {errors}")
                return JsonResponse({'status': 'error', 'errors': errors}, status=400)

            # Create user if all validations pass
            try:
                user = User.objects.create_user(
                    username=account,
                    email=email,
                    password=password
                )
                user.first_name = full_name
                user.save()
                
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Account created successfully'
                })
            
            except Exception as create_error:
                logger.error(f"Error creating user: {create_error}")
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Error creating user: {str(create_error)}'
                }, status=500)
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON data received")
            return JsonResponse({
                'status': 'error', 
                'message': 'Invalid JSON data'
            }, status=400)
        
        except KeyError as key_error:
            return JsonResponse({
                'status': 'error', 
                'message': f'Missing required field: {str(key_error)}'
            }, status=400)
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Unexpected error: {str(e)}'
            }, status=500)


# Initialize language model
MODEL = Ollama(model="llama3.2:1b")
embeddings = OpenAIEmbeddings(api_key=OPENAI_KEY_api)
parser = StrOutputParser()

def load_documents(document_folder: str):
    try:
        # Ensure folder exists
        if not os.path.exists(document_folder):
            os.makedirs(document_folder)
            logger.warning(f"Created document folder: {document_folder}")
            return

        Documents = []
        for filename in os.listdir(document_folder):
            if filename.endswith('.pdf'):
                file_path = os.path.join(document_folder, filename)
                try:
                    loader = PyPDFLoader(file_path)
                    pages = loader.load_and_plit()
                    Documents.extend(pages)
                except Exception as e:
                    logger.error(f"Error loading PDF {filename}: {e}")

        # Create vector store
        vector_store = DocArrayInMemorySearch.from_documents(
            documents=Documents, 
            embedding=embeddings
        )

    except Exception as e:
        logger.error(f"Document loading error: {e}")
        raise

    return vector_store


def retrieve_context(vector_store, query: str, top_k: int = 3) -> str:
    try:
        if not vector_store:
            logger.warning("No documents loaded in the system.")
            return "No documents loaded in the system."

        # Perform similarity search
        retriever = vector_store.as_retriever().retrieve(query)

    except Exception as e:
        logger.error(f"Context retrieval error: {e}")
        return f"Error retrieving context: {e}"
    
    return retriever

def generate_response(query: str, context) -> str:
    try:
        # Prepare input
        prompt = PromptTemplate(
            input_variables = ["context", "question"],
            template = "If this is my first question, please answer it naturally without considering any past context. If this is my second or subsequent question, kindly base your response on my previous context or relevant information, unless specified otherwise. Here's my question: {question}, and please do not remind anything in the past, I know you dont have any information in the beginning but you mustn't tell me like that."
        )

        prompt.format(context=context, question=query) 

        chain = (
            {
                "context": itemgetter(context),
                "question": itemgetter(query),

            }
            | prompt 
            | MODEL 
            | parser
        )

        response = chain.invoke({"question": query})
        logger.info(f"Generated response: {response}")

    except Exception as e:
        logger.error(f"Response generation error: {e}")
        return f"Sorry, I couldn't generate a response. Error: {e}"
    return response

@csrf_exempt  # Remove this in production and use proper CSRF protection
def response_user(request):
    try:
        # Parse JSON data from the request body
        data = json.loads(request.body)
        user_message = data.get('question', '')

        # Optional: Validate message length
        if not user_message:
            return JsonResponse({
                'response': "Please enter a message.",
            }, status=400)

        # Load documents from the vector database
        vector_db = load_documents("/Users/nguyenminhtien/Documents/Visual Code/AI Engineer/BackEnd/data")

        # Retrieve context based on the user's message
        context = retrieve_context(vector_db, user_message)

        # Generate AI response
        response_message = generate_response(user_message, context)

        # Return JSON response for AJAX request
        return JsonResponse({
            'response': response_message,
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'response': "Invalid JSON received. Please try again.",
        }, status=400)

    except Exception as e:
        # Log the error and return a generic error message
        logger.error(f"Error processing message: {e}")
        return JsonResponse({
            'response': "Sorry, something went wrong. Please try again later.",
        }, status=500)
    
def send_otp(request, email):
    """Generate and send an OTP to the specified email address."""
    otp = random.randint(100000, 999999)  # Generate a 6-digit OTP

    subject = 'Your OTP Code'
    message = f'Your OTP code is {otp}. It is valid for 3 minutes.'
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]

    try:
        send_mail(subject, message, from_email, recipient_list)
        request.session['otp'] = str(otp)
        logging.info(f"OTP sent to {email}: {otp}")  # Log the successful sending
        return otp  # Return the generated OTP
    except Exception as e:
        logging.error(f"Error sending email: {e}")  # Log the error
        return None
   
@csrf_exempt     
def reset_password_view(request):
    return render(request, 'reset_password.html')

@csrf_exempt 
def reset_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = request.session.get('reset_email', None)

            logger.info(f"Email received for password reset: {email}")

            new_password = data.get('newPassword', '').strip()
            logger.info(f"new_password received for password reset: {new_password}")
            
            confirm_password = data.get('confirmPassword', '').strip()  # Ensure the key matches
            logger.info(f"confirm_password received for password reset: {confirm_password}")

            # Check if the new password and confirm password match
            if new_password == confirm_password:
                try:
                    user = User.objects.get(email=email)  # Get the user by email
                    user.set_password(new_password)  # Set the new password
                    user.save()  # Save the user object
                    return JsonResponse({'status': "OK", 'message': 'Password changed successfully.'})
                except User.DoesNotExist:
                    logger.error(f"User with email {email} does not exist.")
                    return JsonResponse({'status': False, 'error': 'User does not exist.'}, status=404)
                except Exception as e:
                    logger.error(f"Error changing password for user {email}: {e}")
                    return JsonResponse({'status': False, 'error': 'Cannot change your password.'}, status=500)
            else:
                return JsonResponse({'status': False, 'error': 'Passwords do not match2222.'}, status=400)

        except json.JSONDecodeError:
            logger.error("Invalid JSON data received.")
            return JsonResponse({'status': False, 'error': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({'status': False, 'error': 'An unexpected error occurred.'}, status=500)

    return JsonResponse({'status': False, 'error': 'Invalid request method.'}, status=405)