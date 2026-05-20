def download_video(url: str):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        
        # Самый надёжный вариант без merge
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        
        # Критично для хостингов без ffmpeg
        "merge_output_format": None,
        "postprocessors": [],
        
        # Дополнительная защита
        "prefer_free_formats": True,
        "format_sort": ["ext:mp4", "vcodec:h264"],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        # Принудительно ищем .mp4 файл
        base = os.path.splitext(filename)[0]
        possible_files = [
            base + ".mp4",
            base + ".webm",
            filename
        ]
        
        for f in possible_files:
            if os.path.exists(f):
                return f

        raise Exception("Файл не найден после скачивания")