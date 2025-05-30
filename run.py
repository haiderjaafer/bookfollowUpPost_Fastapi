# run.py (in root folder)
# Import the FastAPI app instance from your main app module
from app.main import app

# Import settings to print out the database URL (for debug/info)
from app.database.config import settings

# Import uvicorn to serve the FastAPI app
import uvicorn
import os


# Print the database connection string (useful for debugging)
#print("Using DB URL:", settings.sqlalchemy_database_url)

host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", 9000))


# Only run the server if this script is executed directly
if __name__ == "__main__":
    # Start the uvicorn ASGI server with:
    # - app location: "app.main:app"
    # - listening on all interfaces (0.0.0.0)
    # - port 9000
    # - reload enabled for hot-reloading on code changes (development only)
    #uvicorn.run("app.main:app", host="0.0.0.0", port=9000, reload=True)
   uvicorn.run(app, host=host, port=port, reload=True,log_level="info")











 # create .env file -> environment variable
   #python -m venv .venv

   # activate before running 
    #source .venv/Scripts/activate

    #py run.py

    # Freeze installed packages into requirements.txt and create file requirements.txt 
    #This command will overwrite your requirements.txt with all installed packages and their exact versions.
    
     #pip freeze > requirements.txt


    # install on another machine
    #   pip install -r requirements.txt
