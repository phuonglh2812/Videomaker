from fastapi import FastAPI, BackgroundTasks, Body, File, UploadFile, Query, Form, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path
import logging
import json
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
import sys
import time

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import modules
from modules.task_history_manager import TaskHistoryManager
from modules.video_cache import VideoCache
from modules.video_cutter_processor import VideoCutterProcessor
from modules.video_processor import VideoProcessor
from MC_video.api import router as mc_router

# Initialize paths
BASE_PATH = Path(__file__).parent.parent
RAW_DIR = BASE_PATH / 'raw'
CUT_DIR = BASE_PATH / 'cut'
USED_DIR = BASE_PATH / 'used'
TEMP_DIR = BASE_PATH / 'temp'
FINAL_DIR = BASE_PATH / 'final'
CACHE_DIR = BASE_PATH / 'cache'

# Create directories
for directory in [RAW_DIR, CUT_DIR, USED_DIR, TEMP_DIR, FINAL_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="Video Processing API",
    description="API for video processing including MC format videos"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processors and managers
video_processor = VideoProcessor(BASE_PATH)
video_cutter = VideoCutterProcessor(raw_dir=RAW_DIR, cut_dir=CUT_DIR)
task_history = TaskHistoryManager(BASE_PATH)
video_cache = VideoCache(cache_file=CACHE_DIR / 'video_cache.json')

def update_task_status(task_id: str, status_data: dict):
    """Update task status and save to history"""
    # Add timestamp
    status_data['updated_at'] = datetime.now().isoformat()
    
    # Save to history
    task_history.save_task(task_id, status_data)

def get_task_status(task_id: str) -> dict:
    """Get task status from history"""
    status = task_history.get_task(task_id)
    if not status:
        return {"status": "not_found"}
    return status

# Create API router for process endpoints
process_router = APIRouter()

@process_router.post("/make")
async def make_final_video(
    background_tasks: BackgroundTasks,
    request: Optional[str] = Form(None),
    audio_path: str = Form(None),
    subtitle_path: str = Form(None),
    overlay1_path: str = Form(None),
    overlay2_path: str = Form(None),
    preset_name: str = Form(None),
    output_name: str = Form(None)
):
    """
    Create final video with:
    - Audio
    - Subtitles
    - Overlays (optional)
    - Preset settings
    """
    try:
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Parse request if provided
        if request:
            try:
                request_data = json.loads(request)
                audio_path = request_data.get('audio_path', audio_path)
                subtitle_path = request_data.get('subtitle_path', subtitle_path)
                overlay1_path = request_data.get('overlay1_path', overlay1_path)
                overlay2_path = request_data.get('overlay2_path', overlay2_path)
                preset_name = request_data.get('preset_name', preset_name)
                output_name = request_data.get('output_name', output_name)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in request")
        
        # Validate required parameters
        if not all([audio_path, subtitle_path, preset_name]):
            raise HTTPException(
                status_code=400,
                detail="Missing required parameters: audio_path, subtitle_path, preset_name"
            )
            
        # Load preset
        preset_path = BASE_PATH / 'presets' / f"{preset_name}.json"
        if not preset_path.exists():
            raise HTTPException(status_code=404, detail=f"Preset {preset_name} not found")
            
        with open(preset_path, 'r') as f:
            subtitle_config = json.load(f)
            
        # Convert paths to Path objects
        paths = {
            'audio': Path(audio_path),
            'subtitle': Path(subtitle_path),
            'overlay1': Path(overlay1_path) if overlay1_path else None,
            'overlay2': Path(overlay2_path) if overlay2_path else None
        }
        
        # Validate all files exist
        for name, path in paths.items():
            if path and not path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"{name} file not found: {path}"
                )
                
        # Initialize status
        update_task_status(task_id, {
            "status": "processing",
            "progress": 0,
            "message": "Starting video processing",
            "created_at": datetime.now().isoformat(),
            "input_files": {
                "audio": str(paths['audio']),
                "subtitle": str(paths['subtitle']),
                "overlay1": str(paths['overlay1']) if paths['overlay1'] else None,
                "overlay2": str(paths['overlay2']) if paths['overlay2'] else None,
            }
        })
        
        # Start processing in background
        background_tasks.add_task(
            make_video_background,
            processor=video_processor,
            task_id=task_id,
            output_name=output_name,
            audio_path=paths['audio'],
            subtitle_path=paths['subtitle'],
            overlay1_path=paths['overlay1'],
            overlay2_path=paths['overlay2'],
            subtitle_config=subtitle_config
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Video processing started"
        }
        
    except Exception as e:
        logging.error(f"Error in make_final_video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def make_video_background(
    processor: VideoProcessor, 
    task_id: str,
    output_name: Optional[str] = None,
    audio_path: Optional[Path] = None,
    subtitle_path: Optional[Path] = None,
    overlay1_path: Optional[Path] = None,
    overlay2_path: Optional[Path] = None,
    subtitle_config: Optional[dict] = None
):
    """Process video in background"""
    try:
        # Update status
        update_task_status(task_id, {
            "status": "processing",
            "progress": 10,
            "message": "Processing video"
        })
        
        # Process video
        output_path = processor.process_video(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            overlay1_path=overlay1_path,
            overlay2_path=overlay2_path,
            subtitle_config=subtitle_config,
            output_name=output_name
        )
        
        # Wait for ffmpeg to fully release files
        time.sleep(2)  # Đợi 2 giây sau khi xử lý xong
        
        # Update status on success
        update_task_status(task_id, {
            "status": "completed",
            "progress": 100,
            "message": "Video processing completed",
            "output_path": str(output_path),
            "completed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error in make_video_background: {str(e)}")
        update_task_status(task_id, {
            "status": "error",
            "progress": 0,
            "message": str(e),
            "error_at": datetime.now().isoformat()
        })

@process_router.get("/status/{task_id}")
async def get_process_status(task_id: str):
    """Get processing status from /api/process/status endpoint"""
    status = get_task_status(task_id)
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """Get processing status from /api/status endpoint (legacy support)"""
    return await get_process_status(task_id)

# Include routers
app.include_router(process_router, prefix="/api/process", tags=["Process"])
app.include_router(mc_router, prefix="/api/mc", tags=["MC"])

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    uvicorn.run(app, host="0.0.0.0", port=5001)
