from flask import Flask, request, jsonify
import subprocess, os, requests, uuid, threading

app = Flask(__name__)
OUTPUT_DIR = "/tmp/videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_file(url, path):
    r = requests.get(url, timeout=60)
    with open(path, 'wb') as f:
        f.write(r.content)

def generate_video(job_id, scenes, script_text, topic):
    work_dir = f"/tmp/{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    
    # 1. Download images
    image_paths = []
    for i, scene in enumerate(scenes):
        img_path = f"{work_dir}/scene_{i:02d}.jpg"
        try:
            download_file(scene['image_url'], img_path)
            image_paths.append(img_path)
        except:
            pass
    
    # 2. Generate audio via Edge TTS
    audio_path = f"{work_dir}/narration.mp3"
    tts_cmd = [
        "edge-tts",
        "--voice", "en-US-GuyNeural",
        "--rate", "-5%",
        "--text", script_text[:4500],
        "--write-media", audio_path
    ]
    subprocess.run(tts_cmd, check=True)
    
    # 3. Get audio duration
    duration_cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", audio_path
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True)
    total_duration = float(result.stdout.strip())
    scene_duration = total_duration / len(image_paths)
    
    # 4. Create video inputs file
    inputs_file = f"{work_dir}/inputs.txt"
    with open(inputs_file, 'w') as f:
        for img_path in image_paths:
            f.write(f"file '{img_path}'\n")
            f.write(f"duration {scene_duration:.2f}\n")
    
    # 5. FFmpeg video assembly
    output_path = f"{OUTPUT_DIR}/{job_id}.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", inputs_file,
        "-i", audio_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1920x1080:fps=30",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-shortest",
        output_path
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    
    # 6. Save completion status
    status_path = f"{OUTPUT_DIR}/{job_id}_status.txt"
    with open(status_path, 'w') as f:
        f.write("done")

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    job_id = str(uuid.uuid4())[:8]
    
    thread = threading.Thread(
        target=generate_video,
        args=(job_id, data['scenes'], data['script_text'], data['topic'])
    )
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "status": "processing",
        "check_url": f"/status/{job_id}"
    })

@app.route('/status/<job_id>')
def status(job_id):
    status_file = f"{OUTPUT_DIR}/{job_id}_status.txt"
    video_file = f"{OUTPUT_DIR}/{job_id}.mp4"
    
    if os.path.exists(status_file):
        return jsonify({
            "status": "done",
            "download_url": f"/download/{job_id}"
        })
    return jsonify({"status": "processing"})

@app.route('/download/<job_id>')
def download(job_id):
    from flask import send_file
    return send_file(f"{OUTPUT_DIR}/{job_id}.mp4", as_attachment=True)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
