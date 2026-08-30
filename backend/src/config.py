
# load_dotenv("/home/dinesh/Desktop/projects/renvue/backend/.env")

# RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
# RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]


from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    razorpay_key_id:str = ""
    razorpay_key_secret:str = ""
    eleven_api_key:str = Field(default="", alias="ELEVENLABS_API_KEY")
    twilo_account_sid:str = Field(default="", alias="TWILO_ACCOUNT_SID")
    twilo_auth_token:str = ""
    resend_api_key:str=""
    twilo_whatsapp_number:str=""
    model:str = ""

settings = Settings()