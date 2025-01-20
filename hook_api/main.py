from fastapi import FastAPI, BackgroundTasks, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path
import logging
import json
from typing import Dict, List, Optional
import uuid
from datetime import datetime
import sys
import time
import os

# Add project root to Python path
BASE_PATH = Path(__file__).parent.parent
sys.path.append(str(BASE_PATH))

# Import modules
from modules import HookVideoProcessor, FileManager, SettingsManager
from modules.task_history_manager import TaskHistoryManager

# Initialize paths
BASE_PATH = Path(__file__).parent.parent
INPUT_16_9_DIR = BASE_PATH / 'Input_16_9'  # For 16:9 videos
INPUT_9_16_DIR = BASE_PATH / 'input_9_16'  # For 9:16 videos
CUT_DIR = BASE_PATH / 'cut'
USED_DIR = BASE_PATH / 'used'
TEMP_DIR = BASE_PATH / 'temp'
FINAL_DIR = BASE_PATH / 'final'

# Create directories
for directory in [INPUT_16_9_DIR, INPUT_9_16_DIR, CUT_DIR, USED_DIR, TEMP_DIR, FINAL_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="Hook Maker API",
    description="API for processing hook videos with subtitles and effects"
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
hook_processor = HookVideoProcessor(BASE_PATH)
file_manager = FileManager(base_path=BASE_PATH, raw_dir=INPUT_16_9_DIR, cut_dir=CUT_DIR)
settings_manager = SettingsManager(base_path=BASE_PATH)
task_history = TaskHistoryManager(BASE_PATH)

def update_task_status(task_id: str, status_data: dict):
    """Update task status and save to history"""
    status_data['updated_at'] = datetime.now().isoformat()
    task_history.save_task(task_id, status_data)

def get_task_status(task_id: str) -> dict:
    """Get task status from history"""
    status = task_history.get_task(task_id)
    if not status:
        return {"status": "not_found"}
    return status

def normalize_settings(settings: Dict) -> Dict:
    """Normalize settings to ensure consistent field names and types"""
    normalized = {}
    
    # Convert all string numbers to integers
    for field in ['font_size', 'margin_v', 'margin_h', 'alignment', 'max_chars']:
        if field in settings:
            normalized[field] = int(str(settings[field]))
    
    # Handle outline and shadow fields
    if 'outline_width' in settings:
        normalized['outline'] = int(str(settings['outline_width']))
    elif 'outline' in settings:
        normalized['outline'] = int(str(settings['outline']))
        
    if 'shadow_width' in settings:
        normalized['shadow'] = int(str(settings['shadow_width']))
    elif 'shadow' in settings:
        normalized['shadow'] = int(str(settings['shadow']))
    
    # Copy string fields as is
    for field in ['font_name', 'primary_color', 'outline_color', 'back_color']:
        if field in settings:
            normalized[field] = str(settings[field])
            
    return normalized

@app.post("/api/v1/hook/process")
async def process_hook_video(
    background_tasks: BackgroundTasks,
    hook_audio: UploadFile = File(..., description="Hook audio file (.mp3 or .wav)"),
    main_audio: UploadFile = File(..., description="Main audio file (.mp3 or .wav)"),
    subtitle_file: UploadFile = File(..., description="Subtitle file (.srt)"),
    thumbnail_file: UploadFile = File(..., description="Thumbnail image (.png)"),
    preset_name: Optional[str] = Form(None),
    subtitle_settings: Optional[str] = Form(None)
):
    """
    Process a single hook video with all required components:
    - Hook audio (required, .mp3 or .wav)
    - Main audio (required, .mp3 or .wav)
    - Subtitle file (required, .srt)
    - Thumbnail (required, .png)
    - Preset name or custom subtitle settings (at least one required)
    """
    try:
        # Validate file types
        if not hook_audio.filename.lower().endswith(('.mp3', '.wav')):
            raise HTTPException(status_code=400, detail="Hook audio must be .mp3 or .wav")
        if not main_audio.filename.lower().endswith(('.mp3', '.wav')):
            raise HTTPException(status_code=400, detail="Main audio must be .mp3 or .wav")
        if not subtitle_file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="Subtitle file must be .srt")
        if not thumbnail_file.filename.lower().endswith('.png'):
            raise HTTPException(status_code=400, detail="Thumbnail must be .png")

        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Save uploaded files
        hook_path = INPUT_16_9_DIR / hook_audio.filename
        main_path = INPUT_16_9_DIR / main_audio.filename
        subtitle_path = INPUT_16_9_DIR / subtitle_file.filename
        thumbnail_path = INPUT_16_9_DIR / thumbnail_file.filename
        
        for file, path in [
            (hook_audio, hook_path),
            (main_audio, main_path),
            (subtitle_file, subtitle_path),
            (thumbnail_file, thumbnail_path)
        ]:
            with open(path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

        # Get subtitle settings
        if preset_name:
            # Ensure preset_name is string
            preset_name = str(preset_name)
            settings = settings_manager.load_preset(preset_name)
            if not settings:
                # Try to load with string version of preset_name
                settings = settings_manager.load_preset(str(preset_name))
                if not settings:
                    available_presets = settings_manager.get_preset_names()
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Preset '{preset_name}' not found. Available presets: {', '.join(available_presets)}"
                    )
        elif subtitle_settings:
            try:
                settings = json.loads(subtitle_settings)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid subtitle settings format")
        else:
            raise HTTPException(status_code=400, detail="Either preset_name or subtitle_settings must be provided")

        # Validate subtitle settings
        required_fields = [
            'font_name', 'font_size', 'primary_color', 'outline_color', 'back_color',
            'outline', 'shadow', 'margin_v', 'margin_h', 'alignment', 'max_chars'
        ]
        
        # Normalize settings
        settings = normalize_settings(settings)
        
        if not all(field in settings for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Missing required subtitle settings: {required_fields}")
        
        # Process video in background
        background_tasks.add_task(
            process_hook_video_background,
            task_id=task_id,
            hook_path=hook_path,
            main_path=main_path,
            subtitle_path=subtitle_path,
            thumbnail_path=thumbnail_path,
            subtitle_settings=settings
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Hook video processing started",
            "input": {
                "hook_audio": hook_audio.filename,
                "main_audio": main_audio.filename,
                "subtitle": subtitle_file.filename,
                "thumbnail": thumbnail_file.filename,
                "preset": preset_name if preset_name else "custom"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing hook video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/batch")
async def process_batch_hooks(
    background_tasks: BackgroundTasks,
    input_folder: str = Form(...),
    preset_name: str = Form(...)
):
    """
    Process multiple hook videos in a folder.
    Files must follow naming convention:
    - Hook audio: *_hook.mp3 or *_hook.wav
    - Main audio: *_audio.mp3 or *_audio.wav
    - Subtitle: *.srt
    - Thumbnail: *_hook.png
    
    Files with matching base names will be processed together.
    """
    try:
        # Validate input folder
        input_path = Path(input_folder)
        if not input_path.exists() or not input_path.is_dir():
            raise HTTPException(status_code=400, detail="Invalid input folder path")
        
        # Get preset settings
        # Ensure preset_name is string
        preset_name = str(preset_name)
        settings = settings_manager.load_preset(preset_name)
        if not settings:
            # Try to load with string version of preset_name
            settings = settings_manager.load_preset(str(preset_name))
            if not settings:
                available_presets = settings_manager.get_preset_names()
                raise HTTPException(
                    status_code=404, 
                    detail=f"Preset '{preset_name}' not found. Available presets: {', '.join(available_presets)}"
                )
                
        # Normalize settings
        settings = normalize_settings(settings)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Process videos in background
        background_tasks.add_task(
            process_batch_videos_background,
            task_id=task_id,
            input_folder=input_path,
            subtitle_settings=settings
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Batch processing started",
            "input": {
                "folder": str(input_path),
                "preset": preset_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/hook/status/{task_id}")
async def get_hook_status(task_id: str):
    """Get status of a hook processing task"""
    status = get_task_status(task_id)
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@app.get("/api/v1/hook/presets")
async def get_presets():
    """Get list of available presets"""
    try:
        presets = settings_manager.get_presets()
        return {
            "status": "success",
            "presets": presets
        }
    except Exception as e:
        logging.error(f"Error getting presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/presets")
async def create_preset(
    preset_name: str = Form(...),
    settings: str = Form(...)
):
    """Create a new subtitle preset"""
    try:
        # Parse settings
        settings_dict = json.loads(settings)
        
        # Validate required fields
        required_fields = [
            'font_name', 'font_size', 'primary_color', 'outline_color', 'back_color',
            'outline', 'shadow', 'margin_v', 'margin_h', 'alignment', 'max_chars'
        ]
        if not all(field in settings_dict for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Missing required fields: {required_fields}")
        
        # Save preset
        settings_manager.save_preset(preset_name, settings_dict)
        
        return {
            "status": "success",
            "message": f"Preset '{preset_name}' created successfully",
            "preset": {
                "name": preset_name,
                "settings": settings_dict
            }
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid settings format")
    except Exception as e:
        logging.error(f"Error creating preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/hook/presets/{preset_name}")
async def delete_preset(preset_name: str):
    """Delete a subtitle preset"""
    try:
        settings_manager.delete_preset(preset_name)
        return {
            "status": "success",
            "message": f"Preset '{preset_name}' deleted successfully"
        }
    except Exception as e:
        logging.error(f"Error deleting preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/process-paths")
async def process_hook_video_paths(
    background_tasks: BackgroundTasks,
    hook_audio_path: str = Form(..., description="Path to hook audio file (.mp3 or .wav)"),
    main_audio_path: str = Form(..., description="Path to main audio file (.mp3 or .wav)"),
    subtitle_path: str = Form(..., description="Path to subtitle file (.srt)"),
    thumbnail_path: str = Form(..., description="Path to thumbnail image (.png)"),
    preset_name: Optional[str] = Form(None),
    subtitle_settings: Optional[str] = Form(None)
):
    """
    Process a single hook video with paths to all required components:
    - Hook audio path (required, .mp3 or .wav)
    - Main audio path (required, .mp3 or .wav)
    - Subtitle path (required, .srt)
    - Thumbnail path (required, .png)
    - Preset name or custom subtitle settings (at least one required)
    """
    try:
        # Convert paths to Path objects
        hook_path = Path(hook_audio_path)
        main_path = Path(main_audio_path)
        subtitle_path = Path(subtitle_path)
        thumbnail_path = Path(thumbnail_path)
        
        # Validate file existence and types
        for path, ext, desc in [
            (hook_path, ('.mp3', '.wav'), "Hook audio"),
            (main_path, ('.mp3', '.wav'), "Main audio"),
            (subtitle_path, ('.srt',), "Subtitle file"),
            (thumbnail_path, ('.png',), "Thumbnail")
        ]:
            if not path.exists():
                raise HTTPException(status_code=400, detail=f"{desc} file not found: {path}")
            if not path.suffix.lower() in ext:
                raise HTTPException(status_code=400, detail=f"{desc} must be {' or '.join(ext)}")

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Get subtitle settings
        if preset_name:
            # Ensure preset_name is string
            preset_name = str(preset_name)
            settings = settings_manager.load_preset(preset_name)
            if not settings:
                # Try to load with string version of preset_name
                settings = settings_manager.load_preset(str(preset_name))
                if not settings:
                    available_presets = settings_manager.get_preset_names()
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Preset '{preset_name}' not found. Available presets: {', '.join(available_presets)}"
                    )
        elif subtitle_settings:
            try:
                settings = json.loads(subtitle_settings)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid subtitle settings format")
        else:
            raise HTTPException(status_code=400, detail="Either preset_name or subtitle_settings must be provided")

        # Validate subtitle settings
        required_fields = [
            'font_name', 'font_size', 'primary_color', 'outline_color', 'back_color',
            'outline', 'shadow', 'margin_v', 'margin_h', 'alignment', 'max_chars'
        ]
        
        # Normalize settings
        settings = normalize_settings(settings)
        
        if not all(field in settings for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Missing required subtitle settings: {required_fields}")
        
        # Process video in background
        background_tasks.add_task(
            process_hook_video_background,
            task_id=task_id,
            hook_path=hook_path,
            main_path=main_path,
            subtitle_path=subtitle_path,
            thumbnail_path=thumbnail_path,
            subtitle_settings=settings
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Hook video processing started",
            "input": {
                "hook_audio": str(hook_path),
                "main_audio": str(main_path),
                "subtitle": str(subtitle_path),
                "thumbnail": str(thumbnail_path),
                "preset": preset_name if preset_name else "custom"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing hook video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/batch-paths")
async def process_batch_hooks_paths(
    background_tasks: BackgroundTasks,
    input_folder: str = Form(...),
    preset_name: str = Form(...)
):
    """
    Process multiple hook videos in a folder using file paths.
    Files must follow naming convention:
    - Hook audio: *_hook.mp3 or *_hook.wav
    - Main audio: *_audio.mp3 or *_audio.wav
    - Subtitle: *.srt
    - Thumbnail: *_hook.png
    
    Files with matching base names will be processed together.
    """
    try:
        # Validate input folder
        input_path = Path(input_folder)
        if not input_path.exists() or not input_path.is_dir():
            raise HTTPException(status_code=400, detail="Invalid input folder path")
        
        # Get preset settings
        # Ensure preset_name is string
        preset_name = str(preset_name)
        settings = settings_manager.load_preset(preset_name)
        if not settings:
            # Try to load with string version of preset_name
            settings = settings_manager.load_preset(str(preset_name))
            if not settings:
                available_presets = settings_manager.get_preset_names()
                raise HTTPException(
                    status_code=404, 
                    detail=f"Preset '{preset_name}' not found. Available presets: {', '.join(available_presets)}"
                )
                
        # Normalize settings
        settings = normalize_settings(settings)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Process videos in background
        background_tasks.add_task(
            process_batch_videos_background,
            task_id=task_id,
            input_folder=input_path,
            subtitle_settings=settings
        )
        
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Batch processing started",
            "input": {
                "folder": str(input_path),
                "preset": preset_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/process_vertical")
async def process_vertical_hook_video(
    background_tasks: BackgroundTasks,
    hook_audio: UploadFile = File(..., description="Hook audio file (.mp3 or .wav)"),
    main_audio: UploadFile = File(..., description="Main audio file (.mp3 or .wav)"),
    subtitle_file: UploadFile = File(..., description="Subtitle file (.srt)"),
    thumbnail_file: UploadFile = File(..., description="Thumbnail image (.png)"),
    preset_name: Optional[str] = Form(None),
    subtitle_settings: Optional[str] = Form(None)
):
    """
    Process a single vertical (9:16) hook video with all required components:
    - Hook audio (.mp3 or .wav)
    - Main audio (.mp3 or .wav)
    - Subtitle (.srt)
    - Thumbnail (.png)
    - Preset name or custom subtitle settings (at least one required)
    """
    try:
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize status
        status_data = {
            "task_id": task_id,
            "status": "started",
            "created_at": datetime.now().isoformat(),
            "type": "vertical_hook",
            "files": {
                "hook_audio": hook_audio.filename,
                "main_audio": main_audio.filename,
                "subtitle": subtitle_file.filename,
                "thumbnail": thumbnail_file.filename
            }
        }
        
        # Update initial status
        update_task_status(task_id, status_data)
        
        # Save uploaded files to vertical temp directory
        temp_dir = TEMP_DIR / "vertical" / task_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        hook_path = temp_dir / hook_audio.filename
        main_path = temp_dir / main_audio.filename
        subtitle_path = temp_dir / subtitle_file.filename
        thumbnail_path = temp_dir / thumbnail_file.filename
        
        # Save files
        for file_obj, save_path in [
            (hook_audio, hook_path),
            (main_audio, main_path),
            (subtitle_file, subtitle_path),
            (thumbnail_file, thumbnail_path)
        ]:
            with open(save_path, "wb") as f:
                f.write(file_obj.file.read())
                
        # Get subtitle settings
        if subtitle_settings:
            try:
                settings = json.loads(subtitle_settings)
                settings = normalize_settings(settings)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid subtitle settings JSON")
        elif preset_name:
            settings = settings_manager.load_preset(preset_name)
            if not settings:
                raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' not found")
        else:
            raise HTTPException(status_code=400, detail="Either preset_name or subtitle_settings is required")
            
        # Set output path to vertical final directory
        output_filename = f"hook_{task_id}.mp4"
        output_path = FINAL_DIR / output_filename
        
        # Process video in background
        background_tasks.add_task(
            process_hook_video_background,
            task_id=task_id,
            hook_path=hook_path,
            main_path=main_path,
            subtitle_path=subtitle_path,
            thumbnail_path=thumbnail_path,
            subtitle_settings=settings,
            is_vertical=True  # Flag for vertical video processing
        )
        
        return {"task_id": task_id, "status": "processing"}
        
    except Exception as e:
        logging.error(f"Error in process_vertical_hook_video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/hook/process_batch_vertical")
async def process_batch_vertical_hooks(
    background_tasks: BackgroundTasks,
    input_folder: str = Form(...),
    preset_name: str = Form(...)
):
    """
    Process multiple vertical (9:16) hook videos.
    
    Args:
        input_folder: Path to folder containing input files with naming convention:
            - Hook audio: *_hook.mp3 or *_hook.wav
            - Main audio: *_audio.mp3 or *_audio.wav
            - Subtitle: *.srt
            - Thumbnail: *_hook.png
        preset_name: Name of the subtitle preset to use
        
    Note: Background videos will be taken from input_9_16 directory
    """
    try:
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Validate input folder
        input_path = Path(input_folder)
        if not input_path.exists():
            raise HTTPException(status_code=404, detail=f"Input folder not found: {input_folder}")
            
        # Validate vertical backgrounds folder exists
        if not INPUT_9_16_DIR.exists():
            raise HTTPException(status_code=404, detail=f"Vertical backgrounds folder not found: {INPUT_9_16_DIR}")
            
        # Load preset settings
        settings = settings_manager.load_preset(preset_name)
        if not settings:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' not found")
            
        # Initialize status
        status_data = {
            "task_id": task_id,
            "status": "started",
            "created_at": datetime.now().isoformat(),
            "type": "batch_vertical_hook",
            "input_folder": str(input_path),
            "preset": preset_name
        }
        
        # Update initial status
        update_task_status(task_id, status_data)
        
        # Process videos in background
        background_tasks.add_task(
            process_batch_videos_background,
            task_id=task_id,
            input_folder=input_path,
            subtitle_settings=settings,
            is_vertical=True  # Flag for vertical video processing
        )
        
        return {"task_id": task_id, "status": "processing"}
        
    except Exception as e:
        logging.error(f"Error in process_batch_vertical_hooks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_hook_video_background(
    task_id: str,
    hook_path: Path,
    main_path: Path,
    subtitle_path: Path,
    thumbnail_path: Path,
    subtitle_settings: Dict,
    is_vertical: bool = False
):
    """Background task for processing single hook video"""
    try:
        # Generate output filename
        output_filename = f"{main_path.stem}_{int(time.time())}.mp4"
        output_path = FINAL_DIR / output_filename
        
        # Process video
        hook_processor.process_hook_video(
            hook_audio=hook_path,
            audio_path=main_path,
            subtitle_path=subtitle_path,
            thumbnail_path=thumbnail_path,
            output_path=output_path,
            subtitle_settings=subtitle_settings,
            is_vertical=is_vertical
        )
        
        # Update task status
        status_data = {
            "task_id": task_id,
            "status": "completed",
            "output_file": str(output_path),
            "completed_at": datetime.now().isoformat()
        }
        update_task_status(task_id, status_data)
        
    except Exception as e:
        logging.error(f"Error in hook video processing: {str(e)}")
        status_data = {
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        }
        update_task_status(task_id, status_data)
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_videos_background(
    task_id: str,
    input_folder: Path,
    subtitle_settings: Dict,
    is_vertical: bool = False
):
    """Background task for processing multiple hook videos"""
    try:
        # Update initial status
        update_task_status(task_id, {
            "status": "processing",
            "message": "Starting batch processing...",
            "progress": 0,
            "processed": 0,
            "total": 0,
            "results": []
        })

        processed_count = 0
        failed_count = 0
        results = []
        
        # Find matching files
        file_groups = {}
        for file in input_folder.glob("*"):
            stem = file.stem.lower()
            
            # Remove suffixes to get base name
            for suffix in ['_hook', '_audio']:
                if stem.endswith(suffix):
                    stem = stem[:-len(suffix)]
            
            # Create group if not exists
            if stem not in file_groups:
                file_groups[stem] = {}
            
            # Classify file
            if '_hook.png' in file.name.lower():
                file_groups[stem]['thumbnail'] = file
            elif '_hook.wav' in file.name.lower() or '_hook.mp3' in file.name.lower():
                file_groups[stem]['hook_audio'] = file
            elif '_audio.wav' in file.name.lower() or '_audio.mp3' in file.name.lower():
                file_groups[stem]['main_audio'] = file
            elif file.suffix.lower() == '.srt':
                file_groups[stem]['subtitle'] = file

        # Update total count
        total_groups = len([g for g in file_groups.values() if len(g) >= 4])
        update_task_status(task_id, {
            "status": "processing",
            "message": f"Found {total_groups} video groups to process",
            "progress": 0,
            "processed": 0,
            "total": total_groups,
            "results": []
        })
        
        # Process complete groups
        for name, group in file_groups.items():
            if len(group) >= 4:  # Must have all required files
                try:
                    # Generate output filename
                    output_filename = f"{name}_{int(time.time())}.mp4"
                    output_path = FINAL_DIR / output_filename
                    
                    # Process video
                    hook_processor.process_hook_video(
                        hook_audio=group['hook_audio'],
                        audio_path=group['main_audio'],
                        thumbnail_path=group['thumbnail'],
                        subtitle_path=group['subtitle'],
                        output_path=output_path,
                        subtitle_settings=subtitle_settings,
                        is_vertical=is_vertical
                    )
                    
                    results.append({
                        "name": name,
                        "status": "success",
                        "output_path": str(output_path)
                    })
                    processed_count += 1
                    
                except Exception as e:
                    results.append({
                        "name": name,
                        "status": "failed",
                        "error": str(e)
                    })
                    failed_count += 1

                # Update progress
                progress = int((processed_count + failed_count) / total_groups * 100)
                update_task_status(task_id, {
                    "status": "processing",
                    "message": f"Processed {processed_count + failed_count} of {total_groups} videos",
                    "progress": progress,
                    "processed": processed_count + failed_count,
                    "total": total_groups,
                    "results": results
                })
        
        # Update final status
        update_task_status(task_id, {
            "status": "completed",
            "processed_count": processed_count,
            "failed_count": failed_count,
            "total": total_groups,
            "results": results,
            "progress": 100,
            "message": f"Batch processing completed. {processed_count} succeeded, {failed_count} failed."
        })
        
    except Exception as e:
        logging.error(f"Error in batch processing: {str(e)}")
        update_task_status(task_id, {
            "status": "failed",
            "error": str(e),
            "message": "Batch processing failed",
            "progress": 0
        })

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run API server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
