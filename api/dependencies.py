from fastapi import HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not api_key_header or api_key_header != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="Could not validate API key"
        )
    return api_key_header

def get_settings():
    return {
        "raw_dir": os.getenv("RAW_DIR", "./raw"),
        "cut_dir": os.getenv("CUT_DIR", "./cut"),
        "used_dir": os.getenv("USED_DIR", "./used"),
        "temp_dir": os.getenv("TEMP_DIR", "./temp"),
        "final_dir": os.getenv("FINAL_DIR", "./final"),
        "min_duration": float(os.getenv("MIN_DURATION", "4.0")),
        "max_duration": float(os.getenv("MAX_DURATION", "7.0")),
    }
