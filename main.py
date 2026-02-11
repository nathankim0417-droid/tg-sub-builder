from fastapi import FastAPI
from app.db import Base, engine
from app.routes import plans, billing, webhooks, status

app = FastAPI(title="TG Sub Builder MVP")

# create tables on startup (easy mode)
Base.metadata.create_all(bind=engine)

app.include_router(plans.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(status.router)

@app.get("/")
def root():
    return {"ok": True}
