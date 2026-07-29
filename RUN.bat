@echo off
chcp 65001 >nul
cd /d "D:\ai video\ai-teaching-video-editor"

echo ============================================================
echo   多平台智能切片工具 - 一键运行
echo ============================================================
echo.

:: 检查 ffmpeg
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] ffmpeg not in PATH, checking .env path...
    :: .env 里配了 FFMPEG 路径，pipeline 会读
)

:: 检查视频
if not exist "input\PNIK4383.MOV" (
    echo [ERROR] input\PNIK4383.MOV not found!
    echo Please put your video in input\ folder
    pause
    exit /b 1
)

echo [OK] Video: input\PNIK4383.MOV
echo.

:: 运行管线 + 导出
echo Starting pipeline...
echo   Step 1: Extract audio
echo   Step 2: ASR speech recognition
echo   Step 3: Scene detection
echo   Step 4: VLM frame description
echo   Step 5: Smart segmentation
echo   Step 6: Score segments
echo   Step 7: Export to douyin/bilibili/xiaohongshu
echo.

py run.py input/PNIK4383.MOV --export

echo.
echo ============================================================
echo   Done! Check output\ folder for exported videos.
echo ============================================================
pause
