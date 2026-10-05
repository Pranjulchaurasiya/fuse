import subprocess
import os

png_path = "github_full_repo.png"
out_mp4 = "test_repo_scroll.mp4"

# Formula:
# if t <= 1.5: y = 0
# if t >= 10.5: y = 5980
# else: y = 5980 * (0.5 - 0.5 * cos(3.14159265 * (t - 1.5) / 9.0))
# Total height = 7060, view height = 1080, max_y = 5980

crop_expr = "if(lte(t,1.5), 0, if(gte(t,10.5), 5980, 5980*(0.5-0.5*cos(3.14159265*(t-1.5)/9.0))))"

cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
    "-loop", "1", "-i", png_path,
    "-vf", f"crop=w=1920:h=1080:x=0:y='{crop_expr}',format=yuv420p",
    "-t", "12",
    "-r", "30",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    out_mp4
]

print("Running FFmpeg...")
subprocess.check_call(cmd)
print("Finished test_repo_scroll.mp4 successfully!")
