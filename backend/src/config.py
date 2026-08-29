
# load_dotenv("/home/dinesh/Desktop/projects/renvue/backend/.env")

# RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
# RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]


from pydantic_settings import BaseSettings
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    razorpay_key_id:str = ""
    razorpay_key_secret:str = ""
    eleven_api_key:str = ""
    twilo_account_sid:str = ""
    twilo_auth_token:str = ""
    resend_api_key:str=""


settings = Settings()