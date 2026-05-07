"""Generate 1200x1500 placeholder JPEGs in seed_images/ for every image referenced from
config.example.yaml. Replace with real photographs before launching."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont


PALETTE = [
    ((230, 222, 208), (180, 150, 110)),  # warm sand → ochre
    ((218, 224, 220), (110, 130, 120)),  # sage → forest
    ((226, 218, 218), (170, 110, 100)),  # blush → terracotta
    ((212, 220, 230), (90, 120, 150)),   # mist → slate blue
    ((222, 218, 228), (140, 110, 160)),  # lilac → aubergine
    ((228, 226, 218), (130, 120, 90)),   # parchment → bronze
]


def yaml_image_paths(config_path: Path) -> list[str]:
    with config_path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    paths: list[str] = []
    for project in data.get('projects') or []:
        if fi := project.get('featured_image'):
            paths.append(fi)
        for g in project.get('gallery') or []:
            if img := g.get('image'):
                paths.append(img)
    return paths


def render(path: Path, label: str, palette_idx: int):
    width, height = 1200, 1500
    top, bottom = PALETTE[palette_idx % len(PALETTE)]
    img = Image.new('RGB', (width, height), top)
    for y in range(height):
        t = y / (height - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        ImageDraw.Draw(img).line([(0, y), (width, y)], fill=(r, g, b))
    img = img.filter(ImageFilter.GaussianBlur(0.5))

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('arial.ttf', 56)
        small = ImageFont.truetype('arial.ttf', 28)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.rectangle([(80, height - 220), (width - 80, height - 80)], outline=(255, 255, 255), width=2)
    draw.text((110, height - 200), label, fill=(255, 255, 255), font=font)
    draw.text((110, height - 130), 'placeholder — replace before deploy', fill=(255, 255, 255), font=small)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, 'JPEG', quality=82, optimize=True)


def main():
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / 'config.example.yaml'
    seed_dir = repo_root / 'seed_images'

    if not config_path.exists():
        print(f'config.example.yaml not found at {config_path}', file=sys.stderr)
        return 1

    paths = yaml_image_paths(config_path)
    if not paths:
        print('No images referenced in YAML.')
        return 0

    for i, rel in enumerate(paths):
        target = seed_dir / rel
        slug = rel.split('/')[0]
        label = f'{slug} · {target.stem}'
        render(target, label, i)
        print(f'  wrote {target.relative_to(repo_root)}')

    print(f'\nGenerated {len(paths)} placeholder images in {seed_dir.relative_to(repo_root)}/')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
