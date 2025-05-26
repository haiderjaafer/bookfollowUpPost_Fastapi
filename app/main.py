from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


# ================= Application Setup =================

from app.database.database import engine , Base
from app.database.config import settings

#print("Using DB URL:", settings.sqlalchemy_database_url)


# all routes imports
from app.routes.bookFollowUp import bookFollowUpRouter
# from app.routes.committee import committee_router
# from app.routes.department import department_router
# from app.routes.estimator import estimatorRouter
# from app.routes.pdf import routerPdf
# from app.routes.procedure import procedureRouter




@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.MODE.upper() == "DEVELOPMENT":   # always safe
        print("🌱 DEVELOPMENT mode: creating database tables...")
        Base.metadata.create_all(bind=engine)
    else:
        print("🚀 PRODUCTION mode: skipping table creation.")

    yield  # always yield after preparing



def create_app() -> FastAPI:
    app = FastAPI(
        title="BookFollowUp API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )

    app.include_router(bookFollowUpRouter)
    # app.include_router(committee_router)
    # app.include_router(department_router)
    # app.include_router( estimatorRouter )
    # app.include_router(routerPdf)  
    # app.include_router(procedureRouter)   
      

 
    return app

app = create_app()

