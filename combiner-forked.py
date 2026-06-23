import ffmpeg
from ffprobe import FFProbe as ffprobe
import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional

def combiner(
    videos: List[str],
    output: str = "video.mp4",
    SILENCE: str = "./SILENCE.mp3",
    print_info: bool = True,
    enforce_fps: Optional[float] = None,
    codec: str = "libx264",
    preset: str = "medium",
    crf: int = 23,
    metadata: Optional[dict] = None
):
    """
    Combines multiple video files into a single output video.
    Optimized for I2V (Image-to-Video) pipelines.
    
    All videos are scaled/padded to the maximum resolution found,
    and any video without audio gets a silent audio track substituted.
    
    Args:
        videos: List of video file paths to combine.
        output: Output file path (default: "video.mp4").
        SILENCE: Path to a silent audio file used for videos without audio.
        print_info: Whether to print progress/info messages.
        enforce_fps: Force all videos to this FPS (if None, use max detected).
        codec: Video codec (default: "libx264").
        preset: Encoding preset: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow.
        crf: Quality (0-51, lower=better, default: 23).
        metadata: Optional metadata dict to add to output.
    """
    maxRes = (0, 0)
    maxFPS = 0
    filteredVids = []

    # Probe each file and collect valid video streams
    for vid in videos:
        if not os.path.exists(vid):
            if print_info:
                print(f"Warning: File {vid} not found, skipping.")
            continue
            
        try:
            r = ffprobe(vid)
        except Exception as e:
            if print_info:
                print(f"Error probing {vid}: {e}, skipping.")
            continue
            
        if r.video:
            vm = r.video[0]
            newVid = (vid, vm, r.audio)
            maxRes = (max(int(vm.width), maxRes[0]), max(int(vm.height), maxRes[1]))
            fps = float(vm.framerate) if vm.framerate else 30.0
            maxFPS = max(fps, maxFPS)
            filteredVids.append(newVid)
        else:
            if print_info:
                print(f"File {vid} does not contain any video streams, skipping.")

    assert len(filteredVids) > 0, "Error: Found no suitable videos."
    
    # Use enforced FPS if provided, otherwise use detected max
    target_fps = enforce_fps if enforce_fps else maxFPS
    if print_info:
        print(f"Combining {len(filteredVids)} videos to {maxRes[0]}x{maxRes[1]}@{target_fps}fps")
    
    preparedVids = []
    for filename, vidProps, audProps in filteredVids:
        # Video stream: scale and pad to maxRes if needed, normalize SAR, enforce FPS
        f = ffmpeg.input(filename).video
        
        # Apply FPS normalization
        if target_fps != float(vidProps.framerate):
            f = f.filter("fps", target_fps)
        
        # Scale and pad if resolution differs
        if (int(vidProps.width), int(vidProps.height)) != maxRes:
            f = f.filter(
                'scale',
                size=f"{maxRes[0]}x{maxRes[1]}",
                force_original_aspect_ratio="decrease"
            )
            f = f.filter('pad', maxRes[0], maxRes[1], "(ow-iw)/2", "(oh-ih)/2")
        
        # Normalize storage aspect ratio
        f = f.filter("setsar", "1")
        preparedVids.append(f)

        # Audio stream: use file's audio or substitute silence
        if audProps:
            preparedVids.append(ffmpeg.input(filename).audio)
        else:
            preparedVids.append(ffmpeg.input(SILENCE).audio)
    
    # Concatenate all segments
    final = (
        ffmpeg
        .concat(*preparedVids, n=len(filteredVids), v=1, a=1)
        .output(
            output,
            vcodec=codec,
            preset=preset,
            crf=crf,
            acodec="aac",
            audio_bitrate="128k"
        )
        .global_args("-y")
        .global_args("-vsync", "2")
        .global_args("-hide_banner")
        .global_args("-loglevel", "error")
    )
    
    if print_info:
        print(f"Encoding video with {codec} (preset={preset}, crf={crf})...")
    
    try:
        final.run()
        if print_info:
            print(f"✓ Finished! Exported video ({maxRes[0]}x{maxRes[1]}p{target_fps})")
            if os.path.exists(output):
                size_mb = os.path.getsize(output) / (1024 * 1024)
                print(f"  Output size: {size_mb:.2f} MB")
    except ffmpeg.Error as e:
        print(f"Error encoding video: {e.stderr.decode()}")
        raise


def batch_combine(input_dir: str, output_dir: str, pattern: str = "*.mp4", **kwargs):
    """
    Batch combine videos from subdirectories.
    
    Args:
        input_dir: Root directory containing video subdirectories.
        output_dir: Directory to save combined videos.
        pattern: File pattern to match (default: "*.mp4").
        **kwargs: Additional arguments passed to combiner().
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for subdir in sorted(os.listdir(input_dir)):
        subdir_path = os.path.join(input_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue
        
        videos = sorted(Path(subdir_path).glob(pattern))
        if not videos:
            print(f"No videos found in {subdir_path}, skipping.")
            continue
        
        output_file = os.path.join(output_dir, f"{subdir}_combined.mp4")
        print(f"\nProcessing {subdir}...")
        combiner([str(v) for v in videos], output_file, **kwargs)


if __name__ == "__main__":
    from os import listdir
    from sys import argv

    output_file = argv[1] if len(argv) > 1 else "video.mp4"
    input_files = (
        argv[2:]
        if len(argv) > 2
        else sorted(["videos/" + i for i in listdir("videos")])
    )
    
    # Optional: Set enforce_fps for I2V pipelines
    # combiner(input_files, output_file, enforce_fps=30.0)
    combiner(input_files, output_file)
