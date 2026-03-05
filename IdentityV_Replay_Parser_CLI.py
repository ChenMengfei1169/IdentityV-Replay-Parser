#!/usr/bin/env python3
"""
Command-line interface for parsing Identity V replay folders.

Reuses core components from the GUI script (IdentityV_Replay_Parser_GUI.py)
to avoid duplication of constants and parsing logic.
"""

import argparse
import csv
import datetime
import json
import logging
import pickle
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional, List

# Import core components from GUI script (assumed to be in the same directory)
try:
    from IdentityV_Replay_Parser_GUI import (
        ReplayParser,
        ReplayInfo,
        MAP_NAMES,
        MODE_NAMES,
        ESCAPE_RES_TYPES,
        find_replay_folders,
        parse_all_replays
    )
except ImportError as e:
    print("Error: Could not import from IdentityV_Replay_Parser_GUI.py", file=sys.stderr)
    print("Make sure the GUI script is in the same directory.", file=sys.stderr)
    # Define missing names to avoid static analysis warnings (program will exit anyway)
    ReplayParser = None
    ReplayInfo = None
    MAP_NAMES = None
    MODE_NAMES = None
    ESCAPE_RES_TYPES = None
    find_replay_folders = None
    parse_all_replays = None
    sys.exit(1)

# =============================================================================
# Helper functions (originally from GUI's ReplayParserGui, kept here for CLI)
# =============================================================================

def _calculate_folder_size(folder_path: Path) -> int:
    """Calculate total size (in bytes) of all files in a folder recursively."""
    total = 0
    for file in folder_path.rglob('*'):
        if file.is_file():
            total += file.stat().st_size
    return total


def _get_timestamp_from_folder(folder_path: Path) -> Optional[float]:
    """Attempt to extract Unix timestamp from game_save_time inside game_info.txt."""
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
    except Exception as _:
        logging.debug(f"Failed to extract timestamp from {folder_path}: {_}")
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
        except Exception as _:
            logging.error(f"Failed to load existing vmap.txt: {_}, will create new.")

    # Ensure all expected keys exist
    for key in list(vmap_data.keys()):
        if key not in vmap_data:
            vmap_data[key] = {}

    folder_size = _calculate_folder_size(folder_path)
    ts = _get_timestamp_from_folder(folder_path)
    if ts is None:
        ts = time.time()

    entry = {"timestamp": ts, "file size": float(folder_size)}
    vmap_data["saved"][hash_value] = entry
    vmap_data["cached"][hash_value] = entry

    try:
        with open(vmap_path, 'wb') as f:
            pickle.dump(vmap_data, f)
        logging.info(f"Updated vmap.txt for {hash_value}")
    except Exception as _:
        logging.error(f"Failed to write vmap.txt: {_}")


# =============================================================================
# CLI-specific export/import functions
# =============================================================================

def export_replay_as_zip(replay_info: ReplayInfo, root_path: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Export a single replay folder as a ZIP archive with descriptive filename.

    Args:
        replay_info: Parsed replay information.
        root_path: Root directory containing the replay folder.
        output_dir: Directory where the ZIP file will be saved.
        force: If True, overwrite existing ZIP file without asking.

    Returns:
        Path to the created ZIP file.

    Raises:
        FileNotFoundError: If the source folder does not exist.
        PermissionError: If unable to write to output directory.
    """
    folder_path = root_path / replay_info["folder_name"]
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f"Replay folder not found: {folder_path}")

    # Generate descriptive filename
    zip_name = f"{replay_info['folder_name']}({replay_info['mode_name']}-{replay_info['date_str']}-{replay_info['time_str']}-{replay_info['result_str']}-{replay_info['map_name']}).zip"
    # Sanitize filename
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        zip_name = zip_name.replace(ch, '_')
    zip_path = output_dir / zip_name

    if zip_path.exists() and not force:
        raise FileExistsError(f"ZIP file already exists: {zip_path} (use --force to overwrite)")

    # Create ZIP archive
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob('*'):
            if file.is_file():
                archive_name = file.relative_to(folder_path.parent)
                zipf.write(file, archive_name)

    return zip_path


def import_zip(zip_path: Path, root_path: Path, force: bool = False) -> str:
    """
    Import a ZIP file (exported by this tool) into the replay root directory.

    Args:
        zip_path: Path to the ZIP file.
        root_path: Replay root directory where the folder will be extracted.
        force: If True, overwrite existing folder without asking.

    Returns:
        The hash (folder name) of the imported replay.

    Raises:
        ValueError: If ZIP filename does not match expected format.
        FileExistsError: If target folder exists and force=False.
    """
    stem = zip_path.stem
    if '(' not in stem or ')' not in stem:
        raise ValueError(f"ZIP filename not in expected format: {zip_path.name}")

    start = stem.find('(')
    hash_part = stem[:start]
    if not hash_part:
        raise ValueError(f"Hash part empty in filename: {zip_path.name}")

    target_folder = root_path / hash_part
    if target_folder.exists():
        if not force:
            raise FileExistsError(f"Target folder already exists: {target_folder} (use --force to overwrite)")
        else:
            shutil.rmtree(target_folder)

    # Extract to temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(tmp_path)

        items = list(tmp_path.iterdir())
        if len(items) == 1 and items[0].is_dir():
            # Single directory: move it to target_folder
            shutil.move(str(items[0]), str(target_folder))
        else:
            # Multiple files: create target folder and move everything
            target_folder.mkdir(parents=True, exist_ok=True)
            for item in items:
                dest = target_folder / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))

    # Update vmap.txt
    update_vmap(root_path, hash_part, target_folder)

    return hash_part


# =============================================================================
# CLI interface
# =============================================================================

def setup_logging(verbose: bool = False) -> None:
    """Configure logging to console."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )


def print_replays(replays: List[ReplayInfo], show_all: bool = False) -> None:
    """Print replay information to console in a human-readable format."""
    for r in replays:
        if r["display_line"].startswith("ERROR:"):
            if show_all:
                print(f"{r['folder_name']} -> {r['display_line']}")
        else:
            print(f"{r['folder_name']} -> {r['display_line']}")


def filter_replays(replays: List[ReplayInfo], filters: List[str]) -> List[ReplayInfo]:
    """
    Filter replays based on key=value conditions.
    Supported keys: mode, date, time, result, map, escape.
    """
    filtered = replays
    for f in filters:
        if '=' not in f:
            logging.warning(f"Ignoring invalid filter: {f} (use key=value)")
            continue
        key, value = f.split('=', 1)
        key = key.strip().lower()
        value = value.strip()

        if key == 'mode':
            filtered = [r for r in filtered if value in r['mode_name']]
        elif key == 'date':
            filtered = [r for r in filtered if value in r['date_str']]
        elif key == 'time':
            filtered = [r for r in filtered if value in r['time_str']]
        elif key == 'result':
            filtered = [r for r in filtered if value in r['result_str']]
        elif key == 'map':
            filtered = [r for r in filtered if value in r['map_name']]
        elif key == 'escape':
            try:
                esc = int(value)
                filtered = [r for r in filtered if r['escape_count'] == esc]
            except ValueError:
                logging.warning(f"Escape count must be integer, got {value}")
        else:
            logging.warning(f"Unknown filter key: {key}")
    return filtered


def export_statistics(replays: List[ReplayInfo], output_path: Path, _format: str = 'csv') -> None:
    """Export replay statistics to CSV or JSON."""
    if _format == 'csv':
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["文件夹哈希", "游戏模式", "日期", "时间", "结果", "地图", "逃生人数"])
            for info in replays:
                if info['display_line'].startswith('ERROR:'):
                    continue
                writer.writerow([
                    info["folder_name"],
                    info["mode_name"],
                    info["date_str"],
                    info["time_str"],
                    info["result_str"],
                    info["map_name"],
                    info["escape_count"]
                ])
    elif _format == 'json':
        data = []
        for info in replays:
            if info['display_line'].startswith('ERROR:'):
                continue
            data.append({
                "folder_name": info["folder_name"],
                "mode": info["mode_name"],
                "date": info["date_str"],
                "time": info["time_str"],
                "result": info["result_str"],
                "map": info["map_name"],
                "escape_count": info["escape_count"]
            })
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"Unsupported export format: {_format}")


def main():
    parser = argparse.ArgumentParser(
        description="Identity V Replay CLI Tool - Parse, export, and import replay files."
    )
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest='command', required=True, help="Subcommands")

    # Parse command
    parse_parser = subparsers.add_parser('parse', help="Parse replay directory and display/export info")
    parse_parser.add_argument('root_dir', type=Path, help="Root directory containing replay folders")
    parse_parser.add_argument('--export-csv', type=Path, help="Export statistics to CSV file")
    parse_parser.add_argument('--export-json', type=Path, help="Export statistics to JSON file")
    parse_parser.add_argument('--filter', action='append', help="Filter results (e.g., --filter result=四抓)")
    parse_parser.add_argument('--show-errors', action='store_true', help="Show parsing errors in output")

    # Export ZIP command
    export_parser = subparsers.add_parser('export', help="Export replay(s) as ZIP")
    export_parser.add_argument('root_dir', type=Path, help="Root directory containing replay folders")
    export_parser.add_argument('--output-dir', '-o', type=Path, default=Path.cwd(),
                               help="Output directory for ZIP files (default: current directory)")
    export_parser.add_argument('--filter', action='append', help="Filter which replays to export")
    export_parser.add_argument('--hash', help="Export a single replay by folder hash (overrides filter)")
    export_parser.add_argument('--force', '-f', action='store_true', help="Overwrite existing ZIP files without asking")

    # Import command
    import_parser = subparsers.add_parser('import', help="Import a ZIP file into replay directory")
    import_parser.add_argument('root_dir', type=Path, help="Replay root directory")
    import_parser.add_argument('zip_file', type=Path, help="ZIP file to import")
    import_parser.add_argument('--force', '-f', action='store_true', help="Overwrite existing folder if present")

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.command == 'parse':
            # Parse replays
            if not args.root_dir.is_dir():
                print(f"Error: {args.root_dir} is not a directory", file=sys.stderr)
                sys.exit(1)

            replays = parse_all_replays(args.root_dir)
            if args.filter:
                replays = filter_replays(replays, args.filter)

            print_replays(replays, show_all=args.show_errors)

            if args.export_csv:
                export_statistics(replays, args.export_csv, _format='csv')
                print(f"Statistics exported to {args.export_csv}")
            if args.export_json:
                export_statistics(replays, args.export_json, _format='json')
                print(f"Statistics exported to {args.export_json}")

        elif args.command == 'export':
            # Export ZIP(s)
            if not args.root_dir.is_dir():
                print(f"Error: {args.root_dir} is not a directory", file=sys.stderr)
                sys.exit(1)

            # Ensure output directory exists
            args.output_dir.mkdir(parents=True, exist_ok=True)

            # Get list of replays
            all_replays = parse_all_replays(args.root_dir)
            valid_replays = [r for r in all_replays if not r['display_line'].startswith('ERROR:')]

            if args.hash:
                # Export single by hash
                target = next((r for r in valid_replays if r['folder_name'] == args.hash), None)
                if not target:
                    print(f"Error: Replay with hash {args.hash} not found or failed parsing", file=sys.stderr)
                    sys.exit(1)
                try:
                    zip_path = export_replay_as_zip(target, args.root_dir, args.output_dir, force=args.force)
                    print(f"Exported: {zip_path}")
                except Exception as _:
                    print(f"Export failed: {_}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Filter and export multiple
                if args.filter:
                    replays_to_export = filter_replays(valid_replays, args.filter)
                else:
                    replays_to_export = valid_replays

                if not replays_to_export:
                    print("No replays match the criteria.", file=sys.stderr)
                    sys.exit(0)

                exported = 0
                failed = 0
                for replay in replays_to_export:
                    try:
                        zip_path = export_replay_as_zip(replay, args.root_dir, args.output_dir, force=args.force)
                        print(f"Exported: {zip_path}")
                        exported += 1
                    except FileExistsError as _:
                        print(f"Skipping {replay['folder_name']}: {_}")
                        failed += 1
                    except Exception as _:
                        print(f"Failed to export {replay['folder_name']}: {_}", file=sys.stderr)
                        failed += 1
                print(f"Export completed: {exported} succeeded, {failed} failed.")

        elif args.command == 'import':
            # Import a ZIP
            if not args.root_dir.is_dir():
                print(f"Error: {args.root_dir} is not a directory", file=sys.stderr)
                sys.exit(1)
            if not args.zip_file.is_file():
                print(f"Error: {args.zip_file} is not a file", file=sys.stderr)
                sys.exit(1)

            try:
                hash_val = import_zip(args.zip_file, args.root_dir, force=args.force)
                print(f"Successfully imported {args.zip_file.name} as folder {hash_val}")
            except Exception as _:
                print(f"Import failed: {_}", file=sys.stderr)
                sys.exit(1)

    except Exception as _:
        logging.exception("Unhandled exception")
        print(f"Fatal error: {_}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()