
# load_dotenv("/home/dinesh/Desktop/projects/renvue/backend/.env")

# RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
# RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    razorpay_key_id:str = ""
    razorpay_key_secret:str = ""


settings = Settings()