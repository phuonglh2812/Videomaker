from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from starlette.status import HTTP_400_BAD_REQUEST
from typing import Dict
import logging
from pathlib import Path

from .models import VideoProcessRequest, VideoResponse, ProcessingStatus
from .dependencies import get_api_key, get_settings
from modules.video_cutter_processor import VideoCutterProcessor
from modules.video_processor import VideoProcessor

router = APIRouter()

# Store processing status
processing_status: Dict[str, ProcessingStatus] = {}

@router.post("/process/cut", response_model=VideoResponse)
async def process_raw_videos(
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks,
    settings: dict = Depends(get_settings),
    api_key: str = Depends(get_api_key)
):
    try:
        # Initialize processor
        processor = VideoCutterProcessor(
            raw_dir=Path(settings["raw_dir"]),
            cut_dir=Path(settings["cut_dir"])
        )
        
        # Start processing in background
        background_tasks.add_task(
            process_videos_background,
            processor,
            request.min_duration,
            request.max_duration
        )
        
        return VideoResponse(
            success=True,
            message="Video processing started in background",
            files=[]
        )
        
    except Exception as e:
        logging.error(f"Error starting video processing: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/process/make", response_model=VideoResponse)
async def make_final_video(
    background_tasks: BackgroundTasks,
    settings: dict = Depends(get_settings),
    api_key: str = Depends(get_api_key)
):
    try:
        # Initialize processor
        processor = VideoProcessor(base_path=Path(settings["raw_dir"]).parent)
        
        # Start processing in background
        background_tasks.add_task(
            make_video_background,
            processor
        )
        
        return VideoResponse(
            success=True,
            message="Video making started in background",
            files=[]
        )
        
    except Exception as e:
        logging.error(f"Error starting video making: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/status/{task_id}", response_model=ProcessingStatus)
async def get_processing_status(
    task_id: str,
    api_key: str = Depends(get_api_key)
):
    if task_id not in processing_status:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Task ID not found"
        )
    return processing_status[task_id]

async def process_videos_background(
    processor: VideoCutterProcessor,
    min_duration: float,
    max_duration: float
):
    try:
        # Get list of raw videos
        raw_videos = list(Path(processor.raw_dir).glob("*.mp4"))
        total = len(raw_videos)
        
        # Update status
        task_id = "cut_task"
        processing_status[task_id] = ProcessingStatus(
            status="running",
            total_videos=total,
            processed_videos=0
        )
        
        # Process each video
        for i, video in enumerate(raw_videos):
            try:
                # Update current video
                processing_status[task_id].current_video = video.name
                
                # Process video
                processor.process_raw_video(
                    video,
                    min_duration=min_duration,
                    max_duration=max_duration
                )
                
                # Update progress
                processing_status[task_id].processed_videos = i + 1
                
            except Exception as e:
                logging.error(f"Error processing video {video}: {str(e)}")
                continue
        
        # Update final status
        processing_status[task_id].status = "completed"
        processing_status[task_id].current_video = None
        
    except Exception as e:
        logging.error(f"Error in background processing: {str(e)}")
        processing_status[task_id] = ProcessingStatus(
            status="error",
            total_videos=0,
            processed_videos=0,
            error=str(e)
        )

async def make_video_background(processor: VideoProcessor):
    try:
        # Update status
        task_id = "make_task"
        processing_status[task_id] = ProcessingStatus(
            status="running",
            total_videos=1,
            processed_videos=0
        )
        
        # Make video
        processor.process_video()
        
        # Update final status
        processing_status[task_id].status = "completed"
        processing_status[task_id].processed_videos = 1
        
    except Exception as e:
        logging.error(f"Error making video: {str(e)}")
        processing_status[task_id] = ProcessingStatus(
            status="error",
            total_videos=1,
            processed_videos=0,
            error=str(e)
        )
