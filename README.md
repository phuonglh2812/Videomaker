# Hook Video Generator

Ứng dụng tự động tạo video hook với subtitle và background nhạc.

## Tính năng

- Tạo video hook từ video gốc
- Thêm subtitle tự động
- Xử lý audio (hook và main)
- Hỗ trợ cả video ngang (16:9) và dọc (9:16)
- API để xử lý hàng loạt video

## Yêu cầu

- Python 3.8+
- FFmpeg
- Các thư viện Python trong `requirements.txt`

## Cài đặt

1. Clone repository:
   ```bash
   git clone <your-repo-url>
   cd hook-video-generator
   ```

2. Cài đặt dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Cài đặt FFmpeg:
   - Windows: Tải từ [FFmpeg website](https://ffmpeg.org/download.html)
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`

4. Tạo file `.env` từ mẫu:
   ```bash
   cp .env.example .env
   ```

## Sử dụng

1. Khởi động server:
   ```bash
   uvicorn hook_api.main:app --reload
   ```

2. API endpoints:
   - POST `/api/v1/hook/process`: Xử lý một video
   - POST `/api/v1/hook/process_batch`: Xử lý nhiều video
   - POST `/api/v1/hook/process_batch_vertical`: Xử lý nhiều video dọc (9:16)

## Cấu trúc thư mục

```
.
├── hook_api/
│   └── main.py
├── modules/
│   ├── hook_video_processor.py
│   ├── hook_background_processor.py
│   ├── subtitle_processor.py
│   └── ...
├── requirements.txt
└── README.md
```

## Cấu hình

Cấu hình được lưu trong file `.env`:
- `INPUT_DIR`: Thư mục chứa video input
- `OUTPUT_DIR`: Thư mục xuất video
- `TEMP_DIR`: Thư mục tạm
- `INPUT_16_9_DIR`: Thư mục video background 16:9
- `INPUT_9_16_DIR`: Thư mục video background 9:16

## License

MIT License
