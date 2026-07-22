import threading
import time
import webbrowser

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analytics import dashboard as analytics_dashboard
from config import (
    APP_URL,
    BACKEND_HOST,
    BACKEND_PORT,
    FRONTEND_DIST_DIR,
    MODE_DESCRIPTIONS,
    VALID_MODES,
)
from scale import dashboard as scale_dashboard

# Store the currently selected operating mode.
current_mode = "analytics"

# Create the FastAPI application.
app = FastAPI(title="DRIVE")


class ModeSelection(BaseModel):
    mode: str


# Return all available operating modes.
@app.get("/api/modes")
def get_modes():
    return {
        mode: {
            "name": f"{mode.title()} Mode",
            "description": description,
        }
        for mode, description in MODE_DESCRIPTIONS.items()
    }


# Return the currently selected operating mode.
@app.get("/api/mode")
def get_mode():
    return {
        "mode": current_mode,
        "description": MODE_DESCRIPTIONS[current_mode],
    }


# Update the currently selected operating mode.
@app.post("/api/mode")
def set_mode(selection: ModeSelection):
    global current_mode

    mode = selection.mode.lower()

    if mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}",
        )

    current_mode = mode

    return {
        "mode": current_mode,
        "description": MODE_DESCRIPTIONS[current_mode],
    }


# Route dashboard requests to the selected mode.
@app.get("/api/dashboard")
def get_dashboard():
    if current_mode == "analytics":
        return analytics_dashboard.get_dashboard_data()

    if current_mode == "scale":
        return scale_dashboard.get_dashboard_data()

    raise HTTPException(
        status_code=500,
        detail="Unable to determine dashboard mode.",
    )


# Return automated analysis for fleet, drive, or comparison views.
@app.get("/api/analysis")
def get_analysis(
    drive_id: str | None = None,
    compare_to: str | None = None,
):
    if current_mode != "analytics":
        raise HTTPException(
            status_code=400,
            detail=(
                "Automated analysis is only available "
                "in Analytics Mode."
            ),
        )

    try:
        return analytics_dashboard.get_analysis_data(
            drive_id=drive_id,
            compare_to=compare_to,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# Serve the compiled React application.
if FRONTEND_DIST_DIR.exists():
    app.mount(
        "/",
        StaticFiles(
            directory=FRONTEND_DIST_DIR,
            html=True,
        ),
        name="frontend",
    )


# Open the browser after the server starts.
def open_browser():
    time.sleep(1)
    webbrowser.open(APP_URL)


# Start the DRIVE application.
def main():
    if not FRONTEND_DIST_DIR.exists():
        print("React build not found.")
        print(
            "Run: cd frontend && "
            "npm install && "
            "npm run build"
        )
        return

    print(f"Starting DRIVE at {APP_URL}")

    threading.Thread(
        target=open_browser,
        daemon=True,
    ).start()

    uvicorn.run(
        app,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
    )


if __name__ == "__main__":
    main()
