from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path

class SubtitleConfig(BaseModel):
    """Cấu hình chi tiết cho phụ đề"""
    font_name: Optional[str] = Field(
        default="Arial", 
        description="Tên font chữ"
    )
    font_size: Optional[int] = Field(
        default=48, 
        description="Kích thước font chữ",
        ge=10, 
        le=100
    )
    primary_color: Optional[str] = Field(
        default='&HFFFFFF&', 
        description="Màu chính của text (định dạng ASS)",
        pattern=r'^&H[0-9A-Fa-f]{6}&$'
    )
    outline_color: Optional[str] = Field(
        default='&H000000&', 
        description="Màu viền của text (định dạng ASS)",
        pattern=r'^&H[0-9A-Fa-f]{6}&$'
    )
    back_color: Optional[str] = Field(
        default='&H000000&', 
        description="Màu nền của text (định dạng ASS)",
        pattern=r'^&H[0-9A-Fa-f]{6}&$'
    )
    outline_width: Optional[float] = Field(
        default=2.0, 
        description="Độ rộng viền text",
        ge=0, 
        le=10
    )
    shadow_width: Optional[float] = Field(
        default=0.0, 
        description="Độ rộng bóng text",
        ge=0, 
        le=10
    )
    margin_v: Optional[int] = Field(
        default=20, 
        description="Margin dọc của text",
        ge=0, 
        le=300
    )
    margin_h: Optional[int] = Field(
        default=20, 
        description="Margin ngang của text",
        ge=0, 
        le=300
    )
    alignment: Optional[int] = Field(
        default=2, 
        description="Vị trí căn chỉnh text (1-9)",
        ge=1, 
        le=9
    )
    max_chars: Optional[int] = Field(
        default=40, 
        description="Số ký tự tối đa trên một dòng",
        ge=10, 
        le=100
    )

    class Config:
        schema_extra = {
            "example": {
                "font_name": "Arial",
                "font_size": 48,
                "primary_color": "&HFFFFFF&",
                "outline_color": "&H000000&",
                "back_color": "&H000000&",
                "outline_width": 2.0,
                "shadow_width": 0.0,
                "margin_v": 20,
                "margin_h": 20,
                "alignment": 2,
                "max_chars": 40
            }
        }

class VideoProcessRequest(BaseModel):
    """Mô hình yêu cầu xử lý video"""
    min_duration: Optional[float] = Field(
        default=4.0, 
        description="Độ dài tối thiểu của mỗi đoạn video (giây)",
        ge=1.0,  # greater than or equal to 1
        le=10.0  # less than or equal to 10
    )
    max_duration: Optional[float] = Field(
        default=7.0, 
        description="Độ dài tối đa của mỗi đoạn video (giây)",
        ge=2.0,  # greater than or equal to 2
        le=15.0  # less than or equal to 15
    )
    
    class Config:
        schema_extra = {
            "example": {
                "min_duration": 4.0,
                "max_duration": 7.0
            }
        }

class VideoMakerRequest(BaseModel):
    """Mô hình yêu cầu tạo video cuối"""
    audio_path: Optional[str] = Field(
        default=None, 
        description="Đường dẫn file âm thanh"
    )
    subtitle_path: Optional[str] = Field(
        default=None, 
        description="Đường dẫn file phụ đề"
    )
    overlay1_path: Optional[str] = Field(
        default=None, 
        description="Đường dẫn file overlay 1"
    )
    overlay2_path: Optional[str] = Field(
        default=None, 
        description="Đường dẫn file overlay 2"
    )
    preset_name: str = Field(
        description="Tên preset cho cấu hình subtitle (ví dụ: 1, 2)"
    )
    output_name: Optional[str] = Field(
        default=None, 
        description="Tên file video đầu ra"
    )

    class Config:
        schema_extra = {
            "example": {
                "audio_path": "E:/RedditWorkflow/3.mp3",
                "subtitle_path": "E:/RedditWorkflow/3.srt",
                "overlay1_path": "E:/RedditWorkflow/overlay.png",
                "overlay2_path": "E:/RedditWorkflow/11.png",
                "preset_name": "1",
                "output_name": "final_video_output.mp4"
            }
        }

class VideoResponse(BaseModel):
    """Mô hình phản hồi sau khi xử lý video"""
    success: Optional[bool] = Field(description="Trạng thái thành công của yêu cầu")
    message: Optional[str] = Field(description="Thông báo chi tiết")
    task_id: Optional[str] = Field(
        default=None, 
        description="ID của task xử lý video để kiểm tra trạng thái"
    )
    files: Optional[List[str]] = Field(
        default=None, 
        description="Danh sách các file video được tạo ra (nếu có)"
    )
    error: Optional[str] = Field(
        default=None, 
        description="Thông báo lỗi (nếu có)"
    )

class ProcessingStatus(BaseModel):
    """Trạng thái xử lý video"""
    status: Optional[str] = Field(
        description="Trạng thái hiện tại: running, completed, error",
        examples=["running", "completed", "error"]
    )
    total_videos: Optional[int] = Field(description="Tổng số video cần xử lý")
    processed_videos: Optional[int] = Field(description="Số video đã xử lý")
    current_video: Optional[str] = Field(
        default=None, 
        description="Tên file video đang được xử lý"
    )
    error: Optional[str] = Field(
        default=None, 
        description="Thông báo lỗi (nếu có)"
    )
