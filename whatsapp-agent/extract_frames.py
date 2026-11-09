# Pull a few evenly spaced still frames out of a video so Claude can "see" it.
# Usage: python extract_frames.py <video> <out dir> [count]  → prints one JPG path per line
import os
import sys

import av


def main() -> None:
    video, out_dir = sys.argv[1], sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    os.makedirs(out_dir, exist_ok=True)
    with av.open(video) as box:
        stream = box.streams.video[0]
        duration = float(box.duration / av.time_base) if box.duration else 0.0
        stamps = [duration * (i + 0.5) / count for i in range(count)] if duration else [0.0]
        paths = []
        for i, t in enumerate(stamps):
            box.seek(int(t / stream.time_base), stream=stream, any_frame=False, backward=True)
            for frame in box.decode(stream):
                if frame.time is None or frame.time >= t - 0.05:
                    img = frame.to_image()
                    img.thumbnail((1280, 1280))
                    path = os.path.join(out_dir, f"frame_{i + 1}_{int(t)}s.jpg")
                    img.save(path, quality=85)
                    paths.append(path)
                    break
    sys.stdout.write("\n".join(paths))


if __name__ == "__main__":
    main()
