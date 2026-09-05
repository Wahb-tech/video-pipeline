import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path


CAR_PALETTES = {
    "midnight_blue": (34, 42, 70),
    "deep_burgundy": (54, 28, 88),
    "graphite": (54, 57, 62),
    "dark_bronze": (38, 64, 82),
}


def palette_for_seed(seed):
    names = tuple(CAR_PALETTES)
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return names[digest[0] % len(names)]


def _run(command, timeout):
    subprocess.run(command, check=True, timeout=timeout)


def recolor_cars(src, start, seconds, destination, seed="zoop"):
    """Subtly recolor confidently segmented cars while preserving scene lighting."""
    import cv2
    import numpy as np
    import torch
    from torchvision.models.segmentation import (
        DeepLabV3_MobileNet_V3_Large_Weights,
        deeplabv3_mobilenet_v3_large,
    )

    timeout = 900
    palette_name = palette_for_seed(seed)
    target_bgr = np.array(CAR_PALETTES[palette_name], dtype=np.float32)
    weights = DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT
    model = deeplabv3_mobilenet_v3_large(weights=weights).eval()
    categories = list(weights.meta.get("categories", ()))
    car_class = categories.index("car") if "car" in categories else 7

    with tempfile.TemporaryDirectory(prefix="zoop_retouch_", dir=Path(destination).parent) as temp_dir:
        temp = Path(temp_dir)
        frames = temp / "frames"
        edited = temp / "edited"
        frames.mkdir()
        edited.mkdir()
        _run([
            "ffmpeg", "-v", "error", "-y", "-ss", f"{float(start):.3f}",
            "-i", str(src), "-t", f"{float(seconds):.3f}", "-an", "-vf", "fps=30",
            str(frames / "frame_%08d.png"),
        ], timeout=180)

        frame_paths = sorted(frames.glob("frame_*.png"))
        if not frame_paths:
            raise RuntimeError("No frames extracted for AI retouch")

        stride = 3
        last_mask = None
        changed_frames = 0
        for index, frame_path in enumerate(frame_paths):
            frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            height, width = frame.shape[:2]
            if index % stride == 0 or last_mask is None:
                inference_width = min(448, width)
                inference_height = max(224, round(height * inference_width / width))
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                resized = cv2.resize(rgb, (inference_width, inference_height), interpolation=cv2.INTER_AREA)
                tensor = torch.from_numpy(resized).permute(2, 0, 1).float().div_(255.0)
                mean = torch.tensor([0.485, 0.456, 0.406])[:, None, None]
                std = torch.tensor([0.229, 0.224, 0.225])[:, None, None]
                tensor = (tensor - mean) / std
                with torch.inference_mode():
                    labels = model(tensor.unsqueeze(0))["out"][0].argmax(0).byte().cpu().numpy()
                mask = (labels == car_class).astype(np.uint8) * 255
                last_mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)

            coverage = float(np.count_nonzero(last_mask)) / float(last_mask.size)
            output = frame
            if 0.015 <= coverage <= 0.80:
                # Keep glass, tyres, deep shadows and headlamps substantially intact.
                # The segmentation model knows where the car is, not which pixels are paint.
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                paint_like = ((hsv[:, :, 2] > 34) & (hsv[:, :, 2] < 236)).astype(np.uint8) * 255
                body_mask = cv2.bitwise_and(last_mask, paint_like)
                feather = cv2.GaussianBlur(body_mask, (0, 0), sigmaX=max(2.0, width / 300))
                alpha = (feather.astype(np.float32) / 255.0 * 0.24)[..., None]
                luminance = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)[..., None]
                colored = np.clip(luminance * 0.72 + target_bgr * 0.28, 0, 255)
                output = np.clip(frame.astype(np.float32) * (1.0 - alpha) + colored * alpha, 0, 255).astype(np.uint8)
                changed_frames += 1
            cv2.imwrite(str(edited / frame_path.name), output, [cv2.IMWRITE_PNG_COMPRESSION, 2])

        _run([
            "ffmpeg", "-v", "error", "-y", "-framerate", "30",
            "-i", str(edited / "frame_%08d.png"), "-an", "-c:v", "ffv1",
            "-level", "3", "-pix_fmt", "yuv420p", str(destination),
        ], timeout=timeout)
        print(f"AI car retouch palette={palette_name} changed_frames={changed_frames}/{len(frame_paths)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--seed", default="zoop")
    args = parser.parse_args()
    recolor_cars(args.input, args.start, args.seconds, args.output, args.seed)


if __name__ == "__main__":
    main()
