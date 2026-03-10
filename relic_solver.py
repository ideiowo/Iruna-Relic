from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Set
import sys
import shutil

import cv2
import numpy as np

BOARD_W = 7
BOARD_H = 7

ALLOWED_COLORS = {"red", "yellow", "white", "blue", "green", "black"}

ATTRIBUTE_SCORE_CELLS = {
    "ATK":  {(0, 0), (1, 1), (2, 2), (3, 3), (5, 5), (6, 6)},
    "ASPD": {(2, 6), (3, 5), (4, 4), (5, 3), (6, 2)},
    "VIT":  {(3, 4), (4, 3), (5, 4), (4, 5)},
    "MATK": {(0, 6), (1, 5), (3, 2), (4, 2), (6, 0)},
    "SSPD": {(2, 4), (4, 0), (4, 1), (5, 0), (5, 2), (6, 1), (6, 2)},
    "INT":  {(2, 3), (3, 2), (3, 4), (4, 3)},
}

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
ASSETS_DIR = BASE_DIR / "assets"
TILES_DIR = ASSETS_DIR / "tiles"
OUT_IMG_DIR = Path.cwd() / "solutions_img"

Cell = Tuple[int, int]


@dataclass(frozen=True)
class Piece:
    pid: str
    name: str
    color: str
    cells: Tuple[Cell, ...]


@dataclass(frozen=True)
class PuzzleConfig:
    board_w: int
    board_h: int
    target: str


@dataclass
class Solution:
    score: int
    rot_k: int
    board: List[List[str]]
    raw_canon: str


def normalize_cells(cells: List[Cell]) -> List[Cell]:
    minx = min(x for x, _ in cells)
    miny = min(y for _, y in cells)
    return [(x - minx, y - miny) for x, y in cells]


def parse_puzzles(path: Path) -> tuple[PuzzleConfig, List[Piece]]:
    lines = path.read_text(encoding="utf-8").splitlines()

    board_w = 7
    board_h = 7
    target = "ATK"

    pieces: List[Piece] = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # skip empty/comment
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        if line.startswith("BOARD="):
            val = line.split("=", 1)[1].strip().lower()
            if "x" not in val:
                raise ValueError(f"Invalid BOARD format: {line}")
            w, h = val.split("x", 1)
            board_w = int(w)
            board_h = int(h)
            i += 1
            continue

        if line.startswith("TARGET="):
            target = line.split("=", 1)[1].strip().upper()
            if target not in ATTRIBUTE_SCORE_CELLS:
                raise ValueError(f"Unsupported TARGET '{target}'. Allowed={list(ATTRIBUTE_SCORE_CELLS.keys())}")
            i += 1
            continue

        # piece block
        if line.startswith("[") and line.endswith("]"):
            pid = line[1:-1].strip()
            if len(pid) != 1:
                raise ValueError(f"Piece id must be 1 char, got '{pid}'")

            i += 1
            if i >= len(lines) or not lines[i].startswith("name="):
                raise ValueError(f"Missing name= for piece [{pid}]")
            name = lines[i].split("=", 1)[1].strip()

            i += 1
            if i >= len(lines) or not lines[i].startswith("color="):
                raise ValueError(f"Missing color= for piece [{pid}]")
            color = lines[i].split("=", 1)[1].strip().lower()
            if color not in ALLOWED_COLORS:
                raise ValueError(f"Piece {pid} has invalid color '{color}'")

            i += 1
            if i >= len(lines) or lines[i].strip() != "shape:":
                raise ValueError(f"Missing shape: for piece [{pid}]")

            i += 1
            shape_lines: List[str] = []
            while i < len(lines):
                cur = lines[i]
                if not cur.strip():
                    break
                if cur.startswith("[") and cur.endswith("]"):
                    break
                shape_lines.append(cur.rstrip("\n"))
                i += 1

            occ: List[Cell] = []
            for y, row in enumerate(shape_lines):
                for x, ch in enumerate(row):
                    if ch != " ":
                        occ.append((x, y))

            if not occ:
                raise ValueError(f"Piece {pid} has empty shape")

            norm = normalize_cells(occ)
            pieces.append(Piece(pid=pid, name=name, color=color, cells=tuple(sorted(norm))))
            continue

        raise ValueError(f"Unrecognized line: {line}")

    return PuzzleConfig(board_w=board_w, board_h=board_h, target=target), pieces


def rotate90_cells(cells: Tuple[Cell, ...]) -> Tuple[Cell, ...]:
    raw = [(y, -x) for x, y in cells]
    minx = min(x for x, _ in raw)
    miny = min(y for _, y in raw)
    norm = [(x - minx, y - miny) for x, y in raw]
    return tuple(sorted(norm))


def unique_rotations(cells: Tuple[Cell, ...]) -> List[Tuple[Cell, ...]]:
    rots: List[Tuple[Cell, ...]] = []
    seen: Set[Tuple[Cell, ...]] = set()
    cur = cells
    for _ in range(4):
        if cur not in seen:
            seen.add(cur)
            rots.append(cur)
        cur = rotate90_cells(cur)
    return rots


def gen_placements(rots: List[Tuple[Cell, ...]], board_w: int, board_h: int) -> List[Tuple[Cell, ...]]:
    placements: List[Tuple[Cell, ...]] = []
    seen: Set[Tuple[Cell, ...]] = set()

    for rcells in rots:
        maxx = max(x for x, _ in rcells)
        maxy = max(y for _, y in rcells)

        for oy in range(board_h - maxy):
            for ox in range(board_w - maxx):
                abs_cells = tuple(sorted((x + ox, y + oy) for x, y in rcells))
                if abs_cells not in seen:
                    seen.add(abs_cells)
                    placements.append(abs_cells)
    return placements


def empty_board(board_w: int, board_h: int) -> List[List[str]]:
    return [["." for _ in range(board_w)] for _ in range(board_h)]


def rotate_board_90(board: List[List[str]]) -> List[List[str]]:
    h, w = len(board), len(board[0])
    out = [["." for _ in range(h)] for _ in range(w)]
    for y in range(h):
        for x in range(w):
            out[x][h - 1 - y] = board[y][x]
    return out


def rotate_board_k(board: List[List[str]], k: int) -> List[List[str]]:
    b = board
    for _ in range(k % 4):
        b = rotate_board_90(b)
    return b


def board_to_string(board: List[List[str]]) -> str:
    return "\n".join("".join(ch if ch != "." else "X" for ch in row) for row in board)


def canonical_board_string_rot_only(board: List[List[str]]) -> str:
    reps = [board_to_string(rotate_board_k(board, k)) for k in range(4)]
    return min(reps)


def clone_board(board: List[List[str]]) -> List[List[str]]:
    return [row[:] for row in board]


def score_board_max_rotation(
    board: List[List[str]],
    pid_to_color: Dict[str, str],
    target_cells: Set[Cell],
) -> Tuple[int, int, List[List[str]]]:
    best_score = -1
    best_k = 0
    best_board = clone_board(board)

    for k in range(4):
        rb = rotate_board_k(board, k)
        s = 0
        for (x, y) in target_cells:
            ch = rb[y][x]
            if ch != "." and pid_to_color.get(ch) == "red":
                s += 1
        if s > best_score:
            best_score = s
            best_k = k
            best_board = clone_board(rb)

    return best_score, best_k, best_board

class Solver:
    def __init__(self, config: PuzzleConfig, pieces: List[Piece], progress_every: int = 5000):
        self.config = config
        self.pieces = pieces
        self.pid_to_color = {p.pid: p.color for p in pieces}

        self.places: Dict[str, List[Tuple[Cell, ...]]] = {}
        for p in pieces:
            rots = unique_rotations(p.cells)
            self.places[p.pid] = gen_placements(rots, config.board_w, config.board_h)

        self.board = empty_board(config.board_w, config.board_h)
        self.occupied: Set[Cell] = set()

        self.tries = 0
        self.progress_every = progress_every
        self.seen_canon: Set[str] = set()
        self.solutions: List[Solution] = []

    def can_place(self, cells: Tuple[Cell, ...]) -> bool:
        return all((x, y) not in self.occupied for x, y in cells)

    def do_place(self, pid: str, cells: Tuple[Cell, ...]) -> None:
        for x, y in cells:
            self.occupied.add((x, y))
            self.board[y][x] = pid

    def undo_place(self, cells: Tuple[Cell, ...]) -> None:
        for x, y in cells:
            self.occupied.remove((x, y))
            self.board[y][x] = "."

    def choose_next_piece(self, remaining: List[str]) -> str:
        best_pid = remaining[0]
        best_cnt = 10**9
        for pid in remaining:
            cnt = 0
            for cells in self.places[pid]:
                if self.can_place(cells):
                    cnt += 1
                    if cnt >= best_cnt:
                        break
            if cnt < best_cnt:
                best_cnt = cnt
                best_pid = pid
        return best_pid

    def solve(self) -> None:
        self._dfs([p.pid for p in self.pieces])
        print(f"[DONE] tried={self.tries:,} solutions={len(self.solutions)}", flush=True)

    def _dfs(self, remaining: List[str]) -> None:
        if not remaining:
            canon = canonical_board_string_rot_only(self.board)
            if canon in self.seen_canon:
                return
            self.seen_canon.add(canon)

            target_cells = ATTRIBUTE_SCORE_CELLS[self.config.target]
            score, rot_k, best_board = score_board_max_rotation(self.board, self.pid_to_color, target_cells)
            self.solutions.append(Solution(score=score, rot_k=rot_k, board=best_board, raw_canon=canon))
            print(f"[FOUND] score={score} target={self.config.target} rot={rot_k*90}deg total_solutions={len(self.solutions)}", flush=True)
            return

        pid = self.choose_next_piece(remaining)
        rest = [x for x in remaining if x != pid]

        for cells in self.places[pid]:
            self.tries += 1
            if self.tries % self.progress_every == 0:
                print(f"[PROGRESS] tried={self.tries:,} solutions={len(self.solutions)}", flush=True)

            if not self.can_place(cells):
                continue

            self.do_place(pid, cells)
            self._dfs(rest)
            self.undo_place(cells)

def draw_label_on_cell(
    canvas_bgra: np.ndarray,
    label: str,
    x: int,
    y: int,
    cell_w: int,
    cell_h: int,
    alpha: float = 0.45,
) -> None:
    """
    在單一格子中央畫半透明英文字母。
    x, y 是該格左上角座標。
    """
    overlay = canvas_bgra.copy()

    font = cv2.FONT_HERSHEY_SIMPLEX

    # 字體大小依格子自動調整
    font_scale = min(cell_w, cell_h) / 55.0
    thickness = max(1, int(min(cell_w, cell_h) / 18))

    # 先計算文字尺寸
    (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    tx = x + (cell_w - tw) // 2
    ty = y + (cell_h + th) // 2

    # 顏色：白字 + 黑描邊，辨識度最高
    outline_color = (0, 0, 0, 255)
    text_color = (255, 255, 255, 255)

    # 在 overlay 上先畫描邊
    cv2.putText(
        overlay,
        label,
        (tx, ty),
        font,
        font_scale,
        outline_color,
        thickness + 2,
        cv2.LINE_AA,
    )

    # 再畫主字
    cv2.putText(
        overlay,
        label,
        (tx, ty),
        font,
        font_scale,
        text_color,
        thickness,
        cv2.LINE_AA,
    )

    # 半透明混合回原圖
    cv2.addWeighted(overlay, alpha, canvas_bgra, 1.0 - alpha, 0, dst=canvas_bgra)

def clear_output_dir(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

def _imwrite_unicode(path: Path, img: np.ndarray) -> None:
    """
    Windows 中文路徑安全版寫圖：
    用 cv2.imencode + tofile，避免 cv2.imwrite 在 Unicode 路徑失敗。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    ext = path.suffix.lower()
    if not ext:
        raise ValueError(f"Output path has no suffix: {path}")

    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"Failed to encode image for: {path}")

    buf.tofile(str(path))

def _imread_rgba(path: Path) -> np.ndarray:
    """
    Windows 中文路徑安全版讀圖：
    用 np.fromfile + cv2.imdecode，避免 cv2.imread 在 Unicode 路徑失敗。
    """
    if not path.exists():
        raise FileNotFoundError(f"Missing image: {path}")

    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        raise FileNotFoundError(f"Image file is empty or unreadable: {path}")

    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Failed to decode image: {path}")

    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    return img


def _alpha_blit(dst_bgra: np.ndarray, src_bgra: np.ndarray, x: int, y: int) -> None:
    h, w = src_bgra.shape[:2]
    H, W = dst_bgra.shape[:2]

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(W, x + w)
    y2 = min(H, y + h)
    if x2 <= x1 or y2 <= y1:
        return

    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    dst_roi = dst_bgra[y1:y2, x1:x2].astype(np.float32)
    src_roi = src_bgra[sy1:sy2, sx1:sx2].astype(np.float32)

    alpha = src_roi[:, :, 3:4] / 255.0
    dst_roi[:, :, :3] = alpha * src_roi[:, :, :3] + (1 - alpha) * dst_roi[:, :, :3]
    dst_roi[:, :, 3] = 255.0

    dst_bgra[y1:y2, x1:x2] = dst_roi.astype(np.uint8)


def load_tiles_scaled_to_min() -> Tuple[Dict[str, np.ndarray], Tuple[int, int]]:
    color_file = {
        "red": "red.png",
        "yellow": "yellow.png",
        "white": "white.png",
        "blue": "blue.png",
        "green": "green.png",
        "black": "black.png",
    }

    color_imgs: Dict[str, np.ndarray] = {}
    sizes: List[Tuple[int, int]] = []

    for color, fname in color_file.items():
        p = TILES_DIR / fname
        img = _imread_rgba(p)
        h, w = img.shape[:2]
        sizes.append((w, h))
        color_imgs[color] = img

    min_w = min(w for w, _ in sizes)
    min_h = min(h for _, h in sizes)

    for color, img in list(color_imgs.items()):
        h, w = img.shape[:2]
        if w != min_w or h != min_h:
            color_imgs[color] = cv2.resize(img, (min_w, min_h), interpolation=cv2.INTER_AREA)

    return color_imgs, (min_w, min_h)

def draw_piece_boundaries(
    canvas_bgra: np.ndarray,
    board_7x7: List[List[str]],
    tile_wh: Tuple[int, int],
    color: Tuple[int, int, int, int] = (255, 0, 0, 255),  # 藍色（BGRA）
    thickness: int = 6,
) -> None:
    """
    為每一組拼圖（同 pid）畫外輪廓粗線。
    只畫不同 pid / 空白 交界處，因此是整組邊界，不是每格小框。
    """
    tile_w, tile_h = tile_wh
    rows = len(board_7x7)
    cols = len(board_7x7[0]) if rows > 0 else 0

    for y in range(rows):
        for x in range(cols):
            pid = board_7x7[y][x]
            if pid == ".":
                continue

            x1 = x * tile_w
            y1 = y * tile_h
            x2 = x1 + tile_w
            y2 = y1 + tile_h

            # 上邊：上方越界或不是同一組
            if y == 0 or board_7x7[y - 1][x] != pid:
                cv2.line(canvas_bgra, (x1, y1), (x2, y1), color, thickness, cv2.LINE_AA)

            # 下邊
            if y == rows - 1 or board_7x7[y + 1][x] != pid:
                cv2.line(canvas_bgra, (x1, y2), (x2, y2), color, thickness, cv2.LINE_AA)

            # 左邊
            if x == 0 or board_7x7[y][x - 1] != pid:
                cv2.line(canvas_bgra, (x1, y1), (x1, y2), color, thickness, cv2.LINE_AA)

            # 右邊
            if x == cols - 1 or board_7x7[y][x + 1] != pid:
                cv2.line(canvas_bgra, (x2, y1), (x2, y2), color, thickness, cv2.LINE_AA)

def build_mosaic_bgra(
    board_7x7: List[List[str]],
    pid_to_color: Dict[str, str],
    tiles: Dict[str, np.ndarray],
    tile_wh: Tuple[int, int],
) -> np.ndarray:
    tile_w, tile_h = tile_wh

    # 透明底
    mosaic = np.zeros((tile_h * 7, tile_w * 7, 4), dtype=np.uint8)

    # 先貼 tile
    for y in range(7):
        for x in range(7):
            pid = board_7x7[y][x]
            if pid == ".":
                continue

            color_name = pid_to_color.get(pid)
            if not color_name:
                continue

            px = x * tile_w
            py = y * tile_h

            tile = tiles[color_name]
            _alpha_blit(mosaic, tile, px, py)

    # 再畫每組拼圖的外輪廓
    draw_piece_boundaries(
        mosaic,
        board_7x7,
        tile_wh,
        color=(255, 0, 0, 255),  # 藍色
        thickness=max(3, min(tile_w, tile_h) // 12),
    )

    return mosaic

def save_sorted_solution_images(solutions: List[Solution], pid_to_color: Dict[str, str]) -> None:
    clear_output_dir(OUT_IMG_DIR)

    solutions_sorted = sorted(solutions, key=lambda s: (-s.score, s.raw_canon))

    tiles, tile_wh = load_tiles_scaled_to_min()

    for i, sol in enumerate(solutions_sorted, 1):
        mosaic = build_mosaic_bgra(sol.board, pid_to_color, tiles, tile_wh)
        out_path = OUT_IMG_DIR / f"solution_{i:03d}_score{sol.score}_rot{sol.rot_k*90}.png"
        _imwrite_unicode(out_path, mosaic)

    print(f"[OUTPUT] saved {len(solutions_sorted)} images into {OUT_IMG_DIR}/", flush=True)


def main():
    puzzle_file = Path.cwd() / "relic_puzzles.txt" 
    if not puzzle_file.exists():
        print("Missing relic_puzzles.txt in current folder.", file=sys.stderr)
        sys.exit(1)

    if not TILES_DIR.exists():
        print(f"Missing tiles directory: {TILES_DIR}", file=sys.stderr)
        sys.exit(1)

    required = ["red.png", "yellow.png", "white.png", "blue.png", "green.png", "black.png"]
    for fname in required:
        if not (TILES_DIR / fname).exists():
            print(f"Missing tile image: {TILES_DIR / fname}", file=sys.stderr)
            sys.exit(1)

    config, pieces = parse_puzzles(puzzle_file)

    total_cells = sum(len(p.cells) for p in pieces)
    if total_cells >= config.board_w * config.board_h:
        print(f"[WARN] total_cells={total_cells} (expected < {config.board_w * config.board_h} by your rule)", file=sys.stderr)

    solver = Solver(config, pieces, progress_every=5000000)
    solver.solve()

    save_sorted_solution_images(solver.solutions, solver.pid_to_color)


if __name__ == "__main__":
    main()