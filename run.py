# run.py (in root folder)
from app.main import app
import uvicorn
from app.database.config import settings

print("Using DB URL:", settings.sqlalchemy_database_url)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=9000, reload=True)


 # create .env file -> environment variable
   #python -m venv .venv

   # activate before running 
    #source .venv/Scripts/activate

    #py run.py

    # create file requirements.txt 
    # #pip freeze > requirements.txt


    # install on another machine
    #   pip install -r requirements.txt
