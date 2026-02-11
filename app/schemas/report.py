from pydantic import BaseModel

class ReportCreate(BaseModel):
    reply_content: str

class ReportUpdate(BaseModel):
    reply_content: str
