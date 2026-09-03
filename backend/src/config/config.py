


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
    redis_url:str = Field(default="", alias="REDIS_URL")
    postgres_url:str=""
    database_url:str=""
    db_pool_size:int=50
    db_max_overflow:int=50
    db_pool_timeout:int=30
    db_pool_recycle:int=1800
    db_checkpointer_pool_size:int=20
    frontend_url:str = ""
    backend_url:str = ""
    demo_mode:bool = False 
    port:int = 8000 

settings = Settings()