import os
from dotenv import load_dotenv
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.db.models import Base
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#loading env variables to validate database url 

load_dotenv()

def get_db_url():
    url = os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('DATABASE_URL is not set in .env')
    return url

#Initializing at global scope, unit tests can be performed without creating a new db connection. 
engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)

def init_db_connection():
    """
    initialization db connection & opens session pool 
    """

    global engine, SessionLocal

    if engine is not None: 
        return #already initialized
    
    db_url = get_db_url()
    retries = 5


    while retries > 0: 
        try:
            engine = create_engine(db_url, pool_pre_ping=True)
            #quick connection test
            connection = engine.connect()
            connection.close()

            logger.info("Succesfully connected to postgres db.")

            SessionLocal.configure(bind=engine)

            Base.metadata.create_all(bind=engine)

            logger.info("Database Schema Synchronized.")

            return
        
        except Exception as e:
            logger.warning(f'Waiting for postgres....(retries left: {retries}). Error: {e}')
            time.sleep(2)
            retries -=1

    raise Exception("Failed to connect to Postgres DB after multiple retries.")
    

def get_db():
    """
    neccessary for FASTAPI 
    """
    if SessionLocal is None:
       init_db_connection()
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()

            







