import os

class Config:
    DATABASE_URL = "sqlite:///./qa_system.db"
    SECRET_KEY = "2bbd5caa6a996d5ab0d6605c2351455494a33799e3c32365"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # Web服務配置
    HOST = "172.20.11.22"
    PORT = 8000
    
    # SSO配置
    SSO_SOAP_WS_URL = "https://odcsso.pthg.gov.tw/SS/SS0/CommonWebService.asmx?WSDL"
    SESSION_COOKIE_SECURE = False  # 如果使用 HTTP 則設為 False
    PERMANENT_SESSION_LIFETIME = 1800

settings = Config()




