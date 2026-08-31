


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
    min_discount:int=0
    max_discount:int=0

settings = Settings()