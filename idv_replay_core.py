"""
Core module for Identity V replay parsing.

Provides shared constants, data structures, parsing logic, and utility functions
used by both GUI and CLI versions of the replay parser.
"""

import datetime
import logging
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, TypedDict, Set

# =============================================================================
# Constants
# =============================================================================

# Known map ID to name mapping.
MAP_NAMES: Dict[int, str] = {
    6: "军工厂",
    11: "红教堂",
    30: "月亮河公园",
    33: "里奥的回忆",
    40: "唐人街",
    18: "圣心医院",
    75: "不归林",
    39: "永眠镇",
    19: "湖景村",
    61: "克雷伯格赛马场",
    32: "白沙街疯人院",
    31: "红教堂(夜)",
    37: "闪金石窟"
}

# Known game mode ID to name mapping.
MODE_NAMES: Dict[int, str] = {
    71: "终场狂欢",
    2: "排位模式",
    1: "匹配模式",
    51: "自定义模式(训练模式)",
    4: "自定义模式(正常模式)",
    79: "独角演出"
}

# Set of res_type values that indicate a survivor has escaped.
ESCAPE_RES_TYPES: Set[int] = {5}


# =============================================================================
# Type definitions
# =============================================================================

class ReplayInfo(TypedDict):
    """
    Type definition for parsed replay information.

    Attributes:
        folder_name (str): Name of the replay folder (hash).
        mode_name (str): Human-readable game mode.
        date_str (str): Date string in "MM月DD日" format.
        time_str (str): Time string in "hh-mm-ss" format.
        result_str (str): Result string (e.g., "四抓", "三跑").
        map_name (str): Map name (Chinese or fallback with ID).
        escape_count (int): Number of escaped survivors.
        display_line (str): Formatted line for display.
    """
    folder_name: str
    mode_name: str
    date_str: str
    time_str: str
    result_str: str
    map_name: str
    escape_count: int
    display_line: str


# =============================================================================
# Core parser class
# =============================================================================

class ReplayParser:
    """
    Parser for a single Identity V replay folder.

    This class reads the `game_info.txt` file inside a replay folder,
    extracts match information, and provides formatted data.

    Attributes:
        folder_path (Path): Path to the replay folder.
        game_data (Optional[Dict]): Parsed data from game_info.txt.
    """

    def __init__(self, folder_path: Path) -> None:
        """
        Initialize the parser with the folder path.

        Args:
            folder_path: Path to the folder containing replay files.

        Raises:
            FileNotFoundError: If the folder does not exist.
        """
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        self.folder_path: Path = folder_path
        self.game_data: Optional[Dict[str, Any]] = None

    def parse_game_info(self) -> Dict[str, Any]:
        """
        Load and parse the game_info.txt file using pickle.

        Returns:
            The deserialized dictionary from game_info.txt.

        Raises:
            FileNotFoundError: If game_info.txt does not exist.
            pickle.UnpicklingError: If the file is corrupted or not a valid pickle.
        """
        info_path = self.folder_path / "game_info.txt"
        if not info_path.exists():
            raise FileNotFoundError(f"Missing game_info.txt in {self.folder_path}")

        with open(info_path, "rb") as f:
            try:
                data = pickle.load(f)
            except Exception as e:
                raise pickle.UnpicklingError(f"Failed to unpickle {info_path}: {e}")
        self.game_data = data
        return data

    def get_escape_count(self) -> int:
        """
        Count the number of survivors who escaped.

        Relies on `all_player_result` list inside game_data.
        Each player entry has 'utype' (1=hunter, 2=survivor) and 'res_type'.
        Escape is defined by `res_type` being in ESCAPE_RES_TYPES.

        Returns:
            Number of escaped survivors (0-4).

        Raises:
            KeyError: If required fields are missing in game_data.
            TypeError: If game_data not loaded.
        """
        if self.game_data is None:
            raise TypeError("game_data not loaded. Call parse_game_info() first.")

        all_players = self.game_data.get("all_player_result", [])
        escape_count = 0
        for player in all_players:
            if player.get("utype") == 2 and player.get("res_type") in ESCAPE_RES_TYPES:
                escape_count += 1
        return escape_count

    def get_result_text(self) -> str:
        """
        Generate a human-readable result based on escape count.

        Mapping:
            - 0 escapes → "四抓" (hunter caught all)
            - 1 escape  → "三抓" (hunter caught three)
            - 2 escapes → "平局" (draw)
            - 3 escapes → "三跑" (survivors three-run)
            - 4 escapes → "四跑" (survivors four-run)

        Returns:
            Result string in Chinese.

        Raises:
            TypeError: If game_data not loaded.
        """
        escapes = self.get_escape_count()
        mapping = {
            0: "四抓",
            1: "三抓",
            2: "平局",
            3: "三跑",
            4: "四跑",
        }
        return mapping.get(escapes, f"未知({escapes}逃)")

    def get_mode_name(self) -> str:
        """
        Get the game mode name from match_type.

        Returns:
            Mode name string (Chinese) or a fallback with the ID if unknown.

        Raises:
            KeyError: If 'match_type' is not found in game_data.
            TypeError: If game_data not loaded.
        """
        if self.game_data is None:
            raise TypeError("game_data not loaded. Call parse_game_info() first.")

        mode_id = self.game_data.get("match_type")
        if mode_id is None:
            raise KeyError("'match_type' not found in game_data.")
        return MODE_NAMES.get(mode_id, f"模式{mode_id}")

    def get_map_name(self) -> str:
        """
        Get the map name from the scene_id or scene_id_copy.

        Returns:
            Map name string (Chinese) or a fallback with the ID if unknown.

        Raises:
            KeyError: If neither 'scene_id' nor 'scene_id_copy' is found.
            TypeError: If game_data not loaded.
        """
        if self.game_data is None:
            raise TypeError("game_data not loaded. Call parse_game_info() first.")

        scene_id = self.game_data.get("scene_id")
        if scene_id is None:
            scene_id = self.game_data.get("scene_id_copy")
        if scene_id is None:
            raise KeyError("Neither 'scene_id' nor 'scene_id_copy' found in game_data.")
        return MAP_NAMES.get(scene_id, f"未知地图({scene_id})")

    def get_date_time(self) -> Tuple[str, str]:
        """
        Extract date and time from game_save_time.

        game_save_time format: "YYYY_MM_DD_hh_mm_ss"

        Returns:
            A tuple (date_str, time_str) where:
                date_str: "MM月DD日" (e.g., "2月14日")
                time_str: "hh-mm-ss" (e.g., "14-58-4")

        Raises:
            KeyError: If 'game_save_time' is not found.
            ValueError: If the string format is invalid.
            TypeError: If game_data not loaded.
        """
        if self.game_data is None:
            raise TypeError("game_data not loaded. Call parse_game_info() first.")

        save_time = self.game_data.get("game_save_time")
        if not save_time:
            raise KeyError("'game_save_time' not found in game_data.")

        try:
            parts = save_time.split("_")
            if len(parts) != 6:
                raise ValueError(f"Unexpected format: {save_time}")
            year, month, day, hour, minute, second = parts
            # Remove leading zeros for month and day
            month_str = str(int(month))
            day_str = str(int(day))
            date_str = f"{month_str}月{day_str}日"
            time_str = f"{hour}-{minute}-{second}"
            return date_str, time_str
        except Exception as e:
            raise ValueError(f"Failed to parse game_save_time '{save_time}': {e}")

    def get_display_line(self) -> str:
        """
        Generate the display line in the format:
            "日期-时间-结果-地图"

        Returns:
            Formatted string.

        Raises:
            Various exceptions from called methods; caller should handle.
        """
        date_str, time_str = self.get_date_time()
        result_str = self.get_result_text()
        map_str = self.get_map_name()
        return f"{date_str}-{time_str}-{result_str}-{map_str}"

    def get_all_info(self) -> ReplayInfo:
        """
        Retrieve all parsed information for export.

        Returns:
            A ReplayInfo dictionary containing all relevant fields.
        """
        date_str, time_str = self.get_date_time()
        result_str = self.get_result_text()
        map_str = self.get_map_name()
        mode_str = self.get_mode_name()
        escape_count = self.get_escape_count()
        display_line = self.get_display_line()
        logging.debug(f"Parsed {self.folder_path.name}: escape_count={escape_count}")
        return ReplayInfo(
            folder_name=self.folder_path.name,
            mode_name=mode_str,
            date_str=date_str,
            time_str=time_str,
            result_str=result_str,
            map_name=map_str,
            escape_count=escape_count,
            display_line=display_line
        )


# =============================================================================
# Helper functions for finding and parsing replays
# =============================================================================

def find_replay_folders(root_path: Path) -> List[Path]:
    """
    Find all subdirectories under root_path that contain a game_info.txt file.

    Args:
        root_path: The directory to scan.

    Returns:
        List of Path objects for each replay folder.
    """
    replay_folders = []
    for item in root_path.iterdir():
        if item.is_dir() and (item / "game_info.txt").exists():
            replay_folders.append(item)
    return replay_folders


def parse_all_replays(root_path: Path) -> List[ReplayInfo]:
    """
    Parse all replay folders under root_path and return detailed information.

    Args:
        root_path: The root directory containing replay folders.

    Returns:
        A list of ReplayInfo dictionaries.
    """
    folders = find_replay_folders(root_path)
    results = []
    for folder in folders:
        parser = ReplayParser(folder)
        try:
            parser.parse_game_info()
            info = parser.get_all_info()
            results.append(info)
        except Exception as e:
            logging.error(f"Failed to parse {folder.name}: {e}")
            # On error, create a minimal info with the error message
            results.append(ReplayInfo(
                folder_name=folder.name,
                mode_name="ERROR",
                date_str="",
                time_str="",
                result_str="",
                map_name="",
                escape_count=-1,
                display_line=f"ERROR: {e}"
            ))
    return results


# =============================================================================
# Utility functions for vmap.txt manipulation
# =============================================================================

def calculate_folder_size(folder_path: Path) -> int:
    """
    Calculate total size (in bytes) of all files in a folder recursively.

    Args:
        folder_path: Path to the folder.

    Returns:
        Total size in bytes.
    """
    total = 0
    for file in folder_path.rglob('*'):
        if file.is_file():
            total += file.stat().st_size
    return total


def get_timestamp_from_folder(folder_path: Path) -> Optional[float]:
    """
    Attempt to extract Unix timestamp from game_save_time inside game_info.txt.

    Returns None if parsing fails.
    """
    game_info = folder_path / "game_info.txt"
    if not game_info.exists():
        return None
    try:
        with open(game_info, 'rb') as f:
            data = pickle.load(f)
        save_time = data.get("game_save_time")
        if save_time and isinstance(save_time, str):
            parts = save_time.split("_")
            if len(parts) == 6:
                year, month, day, hour, minute, second = map(int, parts)
                dt = datetime.datetime(year, month, day, hour, minute, second)
                return dt.timestamp()
    except Exception as e:
        logging.debug(f"Failed to extract timestamp from {folder_path}: {e}")
    return None


def update_vmap(root_path: Path, hash_value: str, folder_path: Path) -> None:
    """
    Update the vmap.txt file in the root directory with the new replay entry.
    Adds to both 'saved' and 'cached' sections for compatibility.
    """
    vmap_path = root_path / "vmap.txt"
    vmap_data = {
        "saved": {},
        "cached": {},
        "last_cached": {},
        "delete": {},
        "hide_saved": {},
        "hide_cached": {}
    }

    # Load existing vmap.txt if present
    if vmap_path.exists():
        try:
            with open(vmap_path, 'rb') as f:
                loaded = pickle.load(f)
                if isinstance(loaded, dict):
                    vmap_data = loaded
                else:
                    logging.warning("vmap.txt has unexpected format, will be overwritten with default.")
        except Exception as e:
            logging.error(f"Failed to load existing vmap.txt: {e}, will create new.")

    # Ensure all expected keys exist
    for key in list(vmap_data.keys()):
        if key not in vmap_data:
            vmap_data[key] = {}

    folder_size = calculate_folder_size(folder_path)
    ts = get_timestamp_from_folder(folder_path)
    if ts is None:
        ts = time.time()

    entry = {"timestamp": ts, "file size": float(folder_size)}
    vmap_data["saved"][hash_value] = entry
    vmap_data["cached"][hash_value] = entry

    try:
        with open(vmap_path, 'wb') as f:
            pickle.dump(vmap_data, f)
        logging.info(f"Updated vmap.txt for {hash_value}")
    except Exception as e:
        logging.error(f"Failed to write vmap.txt: {e}")