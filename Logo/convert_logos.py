#!/usr/bin/env python3
"""
Morphix Logo 批量转换器：JPG → PNG（高质量） + SVG（矢量追踪）
输入：3张 Logo 源图
输出：6个文件（3个 PNG + 3个 SVG）到 Logo/ 目录
"""

import os
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import distance
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
WORKSPACE = Path("/Users/stevenmac/Desktop/工作目录/Morphix")
LOGO_DIR = WORKSPACE / "Logo"
OUTPUT_DIR = LOGO_DIR  # 输出到同一目录

# 源文件映射：(源路径, 输出前缀, 描述)
SOURCES = [
    (
        Path("/Users/stevenmac/Downloads/gpt-image-image_ms8z49qf_6etmm6ngnrb.jpg"),
        "Morphix-brand-overview",
        "品牌整体效果图",
    ),
    (LOGO_DIR / "Logo1-1.jpg", "Morphix-logo-icon", "核心图标（纯猴子分身）"),
    (LOGO_DIR / "Logo1-2.jpg", "Morphix-logo-full", "完整Logo（图标+文字）"),
]

# SVG 向量追踪参数
TRACE_THRESHOLD = 200       # 二值化阈值 (0-255)
PATH_SIMPLIFY_TOLERANCE = 1.5  # Douglas-Peucker 简化容差（像素）
MIN_PATH_LENGTH = 3         # 最小路径点数（过滤噪点）
MAX_IMAGE_DIM = 800         # 追踪时最大尺寸（平衡质量与性能）


def convert_to_png(src: Path, dst: Path) -> Path:
    """JPG → 高质量 PNG（保留透明通道信息，RGBA）"""
    img = Image.open(src).convert("RGBA")
    # 如果原图有接近白色背景，不做透明处理（Logo 图通常不透明）
    if img.mode == "RGBA":
        # 检查是否需要保留为 RGBA
        extrema = img.getextrema()
        if extrema[3][0] >= 255:  # Alpha 全不透明
            img = img.convert("RGB")
    img.save(dst, "PNG", optimize=True)
    print(f"  ✅ PNG: {dst.name} ({img.size[0]}×{img.size[1]})")
    return dst


def trace_contours_to_svg(src: Path, dst: Path) -> Path:
    """
    将位图追踪为矢量 SVG 路径。
    使用多阈值分层追踪 + Douglas-Peucker 路径简化。
    """
    img = Image.open(src).convert("RGB")
    orig_w, orig_h = img.size

    # 缩放到合理尺寸做追踪
    scale = min(1.0, MAX_IMAGE_DIM / max(orig_w, orig_h))
    if scale < 1.0:
        new_size = (int(orig_w * scale), int(orig_h * scale))
        img = img.resize(new_size, Image.LANCZOS)

    arr = np.array(img)
    h, w = arr.shape[:2]

    # 多层颜色分离：黑、金、灰（三色 Logo）
    layers = []
    
    # 黑色层 (R+G+B 均低)
    gray = np.mean(arr, axis=2)
    black_mask = gray < 100
    layers.append(("black", "#1A1A1A", black_mask))

    # 金色层 (R高 G中 B低) — 典型金色调 #D4A037 区域
    gold_mask = (
        (arr[:, :, 0] > 160) &   # R 高
        (arr[:, :, 1] > 120) &   # G 中
        (arr[:, :, 2] < 140) &   # B 低
        (arr[:, :, 0] > arr[:, :, 2] + 30)  # R 明显 > B
    )
    layers.append(("gold", "#D4A037", gold_mask))

    # 浅金色层 (更亮的区域)
    light_gold_mask = (
        (arr[:, :, 0] > 200) &
        (arr[:, :, 1] > 180) &
        (arr[:, :, 2] > 120) &
        (gray > 180)
    )
    layers.append(("light_gold", "#FCE8A8", light_gold_mask))

    # 深灰/文字层
    dark_gray_mask = (gray >= 80) & (gray < 160) & (~black_mask)
    layers.append(("dark_gray", "#2A2A2A", dark_gray_mask))

    # 收集所有路径
    all_paths = []  # list of (color, path_data_string)

    for color_name, hex_color, mask in layers:
        if not np.any(mask):
            continue
        paths = trace_binary_mask(mask, w, h, scale)
        for path_d in paths:
            if len(path_d) > MIN_PATH_LENGTH * 2:  # 至少 MIN_PATH_LENGTH 个点
                all_paths.append((hex_color, path_d))

    if not all_paths:
        # fallback: 用单阈值灰度
        binary = gray < TRACE_THRESHOLD
        paths = trace_binary_mask(binary, w, h, scale)
        for path_d in paths:
            if len(path_d) > MIN_PATH_LENGTH * 2:
                all_paths.append(("#1A1A1A", path_d))

    # 写 SVG 文件
    write_svg(dst, all_paths, orig_w, orig_h)
    print(f"  ✅ SVG: {dst.name} ({orig_w}×{orig_h}, {len(all_paths)} paths)")
    return dst


def trace_binary_mask(mask: np.ndarray, w: int, h: int, scale: float) -> list[str]:
    """
    对二值掩码做轮廓追踪，返回 SVG path d 字符串列表。
    使用 scipy.ndimage.find_contours + Douglas-Peucker 简化。
    """
    paths = []

    # 标记连通区域
    labeled, num_features = ndimage.label(mask)

    for region_id in range(1, num_features + 1):
        region_mask = labeled == region_id
        
        # 获取轮廓点
        contours = find_contour_points(region_mask)
        
        for contour in contours:
            if len(contour) < 3:
                continue
            
            # Douglas-Peucker 简化
            simplified = douglas_peucker(contour, PATH_SIMPLIFY_TOLERANCE)
            
            if len(simplified) < 3:
                continue
            
            # 构建 SVG path d 字符串
            path_d = points_to_path_d(simplified, scale)
            if path_d:
                paths.append(path_d)

    return paths


def find_contour_points(mask: np.ndarray) -> list[np.ndarray]:
    """
    使用边界跟踪提取轮廓点集。
    返回每个独立轮廓的点坐标数组列表。
    """
    contours = []
    visited = set()
    h, w = mask.shape
    
    # 使用 scipy 的形态学找边界
    eroded = ndimage.binary_erosion(mask, iterations=1)
    boundary = mask & ~eroded
    
    # 找所有边界点
    boundary_pts = np.argwhere(boundary)
    
    if len(boundary_pts) == 0:
        return contours
    
    # 从每个未访问的边界点开始跟踪
    for start_idx in range(len(boundary_pts)):
        start = tuple(boundary_pts[start_idx])
        if start in visited:
            continue
        
        # 链式跟踪相邻边界点
        chain = trace_chain(boundary, start, visited)
        if len(chain) >= 3:
            contours.append(np.array(chain))
    
    return contours


def trace_chain(boundary: np.ndarray, start: tuple, visited: set) -> list[tuple]:
    """
    从起点开始跟踪一条连续边界链。
    使用 8-邻域连接。
    """
    chain = []
    current = start
    h, w = boundary.shape
    # 8 方向偏移 (顺时针从右开始)
    directions = [(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1)]
    
    max_steps = boundary.sum() * 2  # 安全上限
    prev_dir = 0
    
    for _ in range(max_steps):
        if current in visited and len(chain) > 0:
            break
        
        chain.append(current)
        visited.add(current)
        
        # 搜索下一个边界点（优先保持方向）
        found = False
        for i in range(8):
            dir_idx = (prev_dir + i) % 8
            dr, dc = directions[dir_idx]
            nr, nc = current[0] + dr, current[1] + dc
            if 0 <= nr < h and 0 <= nc < w and boundary[nr, nc] and (nr, nc) not in visited:
                current = (nr, nc)
                prev_dir = dir_idx
                found = True
                break
        
        if not found:
            # 尝试找任意邻居（包括已访问的，用于闭合）
            for dr, dc in directions:
                nr, nc = current[0] + dr, current[1] + dc
                if 0 <= nr < h and 0 <= nc < w and boundary[nr, nc]:
                    if (nr, nc) == chain[0]:  # 回到起点，闭合
                        chain.append(chain[0])
                    current = (nr, nc)
                    found = True
                    break
            if not found:
                break
    
    return chain


def douglas_peucker(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Douglas-Peucker 路径简化算法"""
    if len(points) <= 2:
        return points
    
    # 找到距离首尾连线最远的点
    start, end = points[0], points[-1]
    vec = end - start
    vec_len_sq = np.dot(vec, vec)
    
    if vec_len_sq == 0:
        dists = np.linalg.norm(points - start, axis=1)
    else:
        t = np.clip(np.dot(points - start, vec) / vec_len_sq, 0, 1)
        proj = start + t[:, np.newaxis] * vec
        dists = np.linalg.norm(points - proj, axis=1)
    
    max_idx = np.argmax(dists)
    max_dist = dists[max_idx]
    
    if max_dist > tolerance:
        left = douglas_peucker(points[:max_idx+1], tolerance)
        right = douglas_peucker(points[max_idx:], tolerance)
        return np.vstack([left[:-1], right])
    else:
        return np.array([start, end])


def points_to_path_d(points: np.ndarray, scale: float) -> str:
    """将点数组转为 SVG path d 属性字符串"""
    if len(points) < 2:
        return ""
    
    # 缩放到原始尺寸
    scaled = points * (1.0 / scale)
    
    parts = [f"M {scaled[0,1]:.1f} {scaled[0,0]:.1f}"]
    for i in range(1, len(scaled)):
        parts.append(f"L {scaled[i,1]:.1f} {scaled[i,0]:.1f}")
    
    parts.append("Z")  # 闭合路径
    return " ".join(parts)


def write_svg(dst: Path, paths: list[tuple[str, str]], width: int, height: int):
    """写入 SVG 文件"""
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        f'  <!-- Morphix Logo - Vector Traced -->',
        f'  <!-- Generated from raster source -->',
    ]
    
    for color, path_d in paths:
        svg_lines.append(
            f'  <path d="{path_d}" fill="{color}" fill-rule="evenodd"/>'
        )
    
    svg_lines.append("</svg>")
    
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


# ── 主流程 ────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 50)
    print("Morphix Logo 格式转换器")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 50)
    
    results = {"png": [], "svg": []}
    
    for src_path, prefix, desc in SOURCES:
        if not src_path.exists():
            print(f"⚠️  跳过（文件不存在）: {src_path}")
            continue
        
        print(f"\n📦 [{prefix}] {desc}")
        print(f"   源文件: {src_path.name}")
        
        # 1. PNG
        png_dst = OUTPUT_DIR / f"{prefix}.png"
        convert_to_png(src_path, png_dst)
        results["png"].append(str(png_dst))
        
        # 2. SVG（向量追踪）
        svg_dst = OUTPUT_DIR / f"{prefix}.svg"
        try:
            trace_contours_to_svg(src_path, svg_dst)
            results["svg"].append(str(svg_dst))
        except Exception as e:
            print(f"  ⚠️ SVG 追踪失败: {e}")
            # fallback: 创建嵌入 PNG 的 SVG
            create_fallback_svg(src_path, svg_dst)
            results["svg"].append(str(svg_dst))
    
    print("\n" + "=" * 50)
    print(f"✅ 完成! 共生成 {len(results['png'])} 个 PNG + {len(results['svg'])} 个 SVG")
    print(f"📁 位置: {OUTPUT_DIR}/")
    print("=" * 50)


def create_fallback_svg(src: Path, dst: Path):
    """Fallback: 将 PNG 嵌入 SVG 容器（非真向量但可用）"""
    img = Image.open(src)
    w, h = img.size
    
    import base64
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <image width="{w}" height="{h}" href="data:image/png;base64,{b64}"/>
</svg>"""
    
    with open(dst, "w") as f:
        f.write(svg_content)
    print(f"  ⚠️ SVG (fallback embedded): {dst.name}")


if __name__ == "__main__":
    main()
