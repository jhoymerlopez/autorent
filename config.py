from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://jhoymerlopez75_db_user:jhoymer2006@cluster0.gonb7za.mongodb.net/alquiler_vehiculos?retryWrites=true&w=majority&appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client["alquiler_vehiculos"]

usuarios_col   = db["usuarios"]
vehiculos_col  = db["vehiculos"]
empleados_col  = db["empleados"]
alquileres_col = db["alquileres"]
pagos_col      = db["pagos"]
multas_col     = db["multas"]
