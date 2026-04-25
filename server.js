const express = require('express');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
const app = express();
app.use(express.json({ limit: '50mb' }));

app.post('/render', async (req, res) => {
  const { audio_url, video_url, title } = req.body;
  const outputPath = `/tmp/output_${Date.now()}.mp4`;
  const audioPath = `/tmp/audio_${Date.now()}.mp3`;
  const videoPath = `/tmp/video_${Date.now()}.mp4`;

  try {
    // Download audio
    const audioRes = await fetch(audio_url);
    const audioBuffer = await audioRes.buffer();
    fs.writeFileSync(audioPath, audioBuffer);

    // Download video
    const videoRes = await fetch(video_url);
    const videoBuffer = await videoRes.buffer();
    fs.writeFileSync(videoPath, videoBuffer);

    // FFmpeg merge
    const cmd = `ffmpeg -i ${videoPath} -i ${audioPath} -c:v copy -c:a aac -shortest ${outputPath}`;
    
    exec(cmd, async (error) => {
      if (error) return res.status(500).json({ error: error.message });
      
      const videoData = fs.readFileSync(outputPath);
      const base64 = videoData.toString('base64');
      
      // Cleanup
      fs.unlinkSync(audioPath);
      fs.unlinkSync(videoPath);
      fs.unlinkSync(outputPath);
      
      res.json({ success: true, video_base64: base64 });
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(process.env.PORT || 3000, () => {
  console.log('FFmpeg server running');
});
