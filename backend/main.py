from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
from faster_whisper import WhisperModel
import os
import re
import json
import asyncio

app = FastAPI()

print("Loading High-Accuracy Whisper Model...")
model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=8)

class VideoRequest(BaseModel):
    url: str
    custom_keywords: str

async def video_streamer(url: str, custom_keywords: str, request: Request):
    temp_audio_file = f"temp_{id(request)}.wav"
    
    try:
        yield json.dumps({"status": "progress", "step": "Downloading audio...", "percent": 10}) + "\n"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav', 'preferredquality': '192'}],
            'outtmpl': temp_audio_file.replace('.wav', ''),
            'quiet': True
        }
        
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        if await request.is_disconnected(): return 

        yield json.dumps({"status": "progress", "step": "Transcribing Telugu audio...", "percent": 30}) + "\n"
        
        segments, info = model.transcribe(
            temp_audio_file, 
            language="te", 
            beam_size=5, 
            vad_filter=True,
            condition_on_previous_text=False 
        )
        duration = info.duration
        
        flagged_results = []
        full_transcript = "" 
        
        keyword_list = [w.strip() for w in custom_keywords.split(",")] if custom_keywords else []
        pattern = re.compile(r'(?<!\w)(' + '|'.join(map(re.escape, keyword_list)) + r')', re.IGNORECASE) if keyword_list else None

        for segment in segments:
            if await request.is_disconnected(): return 

            text = segment.text.strip()
            timestamp_str = f"[{int(segment.start//60):02}:{int(segment.start%60):02}]"
            full_transcript += f"{timestamp_str} {text}\n"
            
            if pattern:
                matches = pattern.findall(text)
                if matches:
                    flagged_results.append({
                        "timestamp": round(segment.start, 2),
                        "text": text,
                        "matched_words": list(set(matches))
                    })
            
            prog = 30 + int((segment.end / duration) * 65) if duration > 0 else 90
            pct_val = min(prog, 98) 
            yield json.dumps({
                "status": "progress", 
                "step": f"Processing AI segments...", 
                "percent": pct_val
            }) + "\n"
            await asyncio.sleep(0.01)

        yield json.dumps({
            "status": "complete", 
            "data": {"language": info.language, "flags": flagged_results, "full_transcript": full_transcript}
        }) + "\n"

    except Exception as e:
        yield json.dumps({"status": "error", "message": str(e)}) + "\n"
    finally:
        if os.path.exists(temp_audio_file): os.remove(temp_audio_file)

@app.post("/scan-video/")
async def scan_video(request: Request):
    body = await request.json()
    return StreamingResponse(video_streamer(body['url'], body['custom_keywords'], request), media_type="application/x-ndjson")