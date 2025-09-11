from fastapi import FastAPI
from dbconfig import lifespan
app = FastAPI(lifespan=lifespan)
