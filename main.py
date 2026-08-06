"""Run the DRIVE Analytics pipeline and serve the React/FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analytics.aggregate import build_aggregate
from analytics.critical import build_critical_scenarios
from analytics.dashboard import get_dashboard_data, get_scenario_data
from analytics.events import build_events
from analytics.insights import build_insights
from analytics.scenarios import build_scenarios
from config import BACKEND_HOST, BACKEND_PORT, FRONTEND_DIST_DIR
from telemetry import run_pipeline, summarize_pipeline


FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
LOCAL_FRONTEND_URLS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def run_analytics_pipeline() -> dict:
    """Build all persisted Analytics Mode datasets in dependency order."""

    print("Starting DRIVE analytics pipeline...")

    print("1/6 Building telemetry...")
    result = run_pipeline()
    summary = summarize_pipeline(result)

    if summary["files_processed"] == 0:
        raise RuntimeError(
            "No telemetry CSV files were found. Add the Tesla Model 3 "
            "dataset to the configured telemetry directory before starting "
            "DRIVE."
        )

    print(
        "Telemetry complete: "
        f"{summary['files_processed']} files, "
        f"{summary['rows_served']} rows served."
    )

    print("2/6 Building AP disengagement events...")
    build_events()

    print("3/6 Building scenario context...")
    build_scenarios()

    print("4/6 Building aggregate temporal analysis...")
    build_aggregate()

    print("5/6 Detecting critical scenarios...")
    build_critical_scenarios()

    print("6/6 Building final insights...")
    build_insights()

    print("DRIVE analytics pipeline completed.")
    return summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build analytics datasets before the application accepts requests."""

    run_analytics_pipeline()
    yield


app = FastAPI(
    title="DRIVE API",
    description="Data Reporting Infrastructure for Vehicle Events",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ASSETS_DIR),
        name="assets",
    )


@app.get("/api/health")
def get_health() -> dict[str, str]:
    """Return the service health status."""

    return {
        "status": "healthy",
        "service": "DRIVE",
    }


@app.get("/api/analysis")
def analysis() -> dict:
    """Return the complete read-only Analytics Mode dashboard response."""

    try:
        return get_dashboard_data()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str) -> dict:
    """Return one selected critical scenario for temporal drill-down."""

    try:
        return get_scenario_data(scenario_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


def _frontend_index() -> FileResponse:
    """Return the built React entry page or explain how to create it."""

    if not FRONTEND_INDEX_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                "Frontend build not found at "
                f"'{FRONTEND_INDEX_PATH}'. Run 'npm run build' in the "
                "frontend directory first."
            ),
        )

    return FileResponse(FRONTEND_INDEX_PATH)


@app.get("/")
def serve_frontend() -> FileResponse:
    """Serve the built React application."""

    return _frontend_index()


@app.get("/{full_path:path}")
def serve_react_app(full_path: str) -> FileResponse:
    """Serve static frontend files and fall back to React client routing."""

    requested_path = (FRONTEND_DIST_DIR / full_path).resolve()
    frontend_root = FRONTEND_DIST_DIR.resolve()

    if requested_path.is_relative_to(frontend_root) and requested_path.is_file():
        return FileResponse(requested_path)

    return _frontend_index()


def open_browser() -> None:
    """Open the local dashboard when running directly outside Docker."""

    import threading
    import webbrowser

    def _open() -> None:
        webbrowser.open(f"http://{BACKEND_HOST}:{BACKEND_PORT}")

    threading.Timer(1.0, _open).start()


if __name__ == "__main__":
    import uvicorn

    open_browser()

    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=False,
    )
