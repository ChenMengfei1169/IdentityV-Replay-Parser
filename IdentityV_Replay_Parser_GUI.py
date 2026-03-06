"""
Graphical user interface for parsing Identity V replay folders.

Allows selecting replay root directory, parsing all replays,
displaying results, and exporting selected replays as ZIP archives
or exporting statistics as CSV. Also supports importing previously exported
ZIP files (with descriptive names) and extracting them back to the replay folder.
"""

import csv
import json
import logging
import shutil
import sys
import tempfile
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

# Import core components from shared module
from idv_replay_core import (
    ReplayInfo,
    parse_all_replays,
    update_vmap
)


# =============================================================================
# Helper to get base directory (works for script and exe)
# =============================================================================
def get_base_dir() -> Path:
    """
    Return the directory where the executable or script is located.

    Returns:
        Path to the base directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


# =============================================================================
# GUI Application
# =============================================================================

# Default root directory for replay folders (used only if no config file).
DEFAULT_ROOT_PATH: str = ""


class ReplayParserGui:
    """
    GUI application for parsing and exporting Identity V replay information.
    """

    def __init__(self, master: tk.Tk) -> None:
        """
        Initialize the GUI.

        Args:
            master: The root tkinter window.
        """
        self.master = master
        master.title("第五人格录像解析器")
        master.geometry("850x650")
        logging.info("GUI initialized")

        # Base directory (where exe/script is located)
        self.base_dir = get_base_dir()
        self.config_file = self.base_dir / "config.json"

        # Store parsed results for export
        self.parsed_results: List[ReplayInfo] = []

        # =====================================================================
        # Top frame: directory selection (replay root)
        # =====================================================================
        top_frame = tk.Frame(master)
        top_frame.pack(pady=10, padx=10, fill=tk.X)  # type: ignore

        tk.Label(top_frame, text="录像根目录:").pack(side=tk.LEFT)  # type: ignore

        self.dir_var = tk.StringVar()
        self.dir_var.set(DEFAULT_ROOT_PATH)
        self.dir_entry = tk.Entry(top_frame, textvariable=self.dir_var, width=50)
        self.dir_entry.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.browse_button = tk.Button(
            top_frame, text="浏览", command=self.select_directory
        )
        self.browse_button.pack(side=tk.LEFT)  # type: ignore

        # =====================================================================
        # Export path frame: directory for saving ZIP files
        # =====================================================================
        export_frame = tk.Frame(master)
        export_frame.pack(pady=5, padx=10, fill=tk.X)  # type: ignore

        tk.Label(export_frame, text="导出路径:").pack(side=tk.LEFT)  # type: ignore

        self.export_dir_var = tk.StringVar()
        self.export_dir_var.set("")
        self.export_dir_entry = tk.Entry(export_frame, textvariable=self.export_dir_var, width=50)
        self.export_dir_entry.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.export_browse_button = tk.Button(
            export_frame, text="浏览", command=self.select_export_directory
        )
        self.export_browse_button.pack(side=tk.LEFT)  # type: ignore

        # =====================================================================
        # Middle frame: parse, export and import buttons
        # =====================================================================
        mid_frame = tk.Frame(master)
        mid_frame.pack(pady=5)

        self.parse_button = tk.Button(
            mid_frame, text="解析录像", command=self.parse_replays
        )
        self.parse_button.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.export_zip_button = tk.Button(
            mid_frame, text="导出为ZIP", command=self.export_as_zip, state=tk.DISABLED  # type: ignore
        )
        self.export_zip_button.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.export_stats_button = tk.Button(
            mid_frame, text="导出统计数据", command=self.export_statistics, state=tk.DISABLED  # type: ignore
        )
        self.export_stats_button.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.import_zip_button = tk.Button(
            mid_frame, text="导入ZIP", command=self.import_zips
        )
        self.import_zip_button.pack(side=tk.LEFT, padx=5)  # type: ignore

        self.status_label = tk.Label(mid_frame, text="")
        self.status_label.pack(side=tk.LEFT, padx=20)  # type: ignore

        # =====================================================================
        # Bottom frame: listbox with scrollbar for results
        # =====================================================================
        bottom_frame = tk.Frame(master)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)  # type: ignore

        scrollbar = tk.Scrollbar(bottom_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # type: ignore

        self.result_listbox = tk.Listbox(
            bottom_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            font=("Consolas", 10)
        )
        self.result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # type: ignore
        scrollbar.config(command=self.result_listbox.yview)

        # Bind selection event to enable ZIP export button
        self.result_listbox.bind('<<ListboxSelect>>', self.on_select)

        # Load saved paths from config file (if any)
        self.load_config()

        # Set window close handler to save configuration
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self) -> None:
        """Load saved paths from config.json (if exists) and set the variables."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                root_path = config.get("root_path", "")
                export_path = config.get("export_path", "")
                if root_path:
                    self.dir_var.set(root_path)
                if export_path:
                    self.export_dir_var.set(export_path)
                logging.info(f"Loaded config: root_path={root_path}, export_path={export_path}")
            except Exception as e:
                logging.warning(f"Failed to load config file: {e}")

    def save_config(self) -> None:
        """Save current root_path and export_path to config.json."""
        config = {
            "root_path": self.dir_var.get().strip(),
            "export_path": self.export_dir_var.get().strip()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logging.info("Configuration saved.")
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def on_closing(self) -> None:
        """Handle window closing: save config and destroy window."""
        self.save_config()
        self.master.destroy()

    def select_directory(self) -> None:
        """Open directory selection dialog for replay root and set the path."""
        directory = filedialog.askdirectory(title="选择录像根目录")
        if directory:
            self.dir_var.set(directory)
            self.save_config()
            logging.info(f"Directory selected: {directory}")

    def select_export_directory(self) -> None:
        """Open directory selection dialog for export path and set the path."""
        directory = filedialog.askdirectory(title="选择导出目录")
        if directory:
            self.export_dir_var.set(directory)
            self.save_config()
            logging.info(f"Export directory selected: {directory}")

    def parse_replays(self) -> None:
        """Parse all replays in the selected directory and display results."""
        dir_path = self.dir_var.get().strip()
        if not dir_path:
            messagebox.showerror("错误", "请先选择录像根目录")
            logging.warning("Parse attempted without selecting directory")
            return

        root = Path(dir_path)
        if not root.exists() or not root.is_dir():
            messagebox.showerror("错误", f"目录不存在或不是文件夹: {root}")
            logging.error(f"Invalid directory: {root}")
            return

        # Clear previous results
        self.result_listbox.delete(0, tk.END)
        self.status_label.config(text="正在解析...")
        self.master.update_idletasks()
        self.export_zip_button.config(state=tk.DISABLED)  # type: ignore
        self.export_stats_button.config(state=tk.DISABLED)  # type: ignore

        logging.info(f"Starting parsing for directory: {root}")
        try:
            self.parsed_results = parse_all_replays(root)
            success_count = sum(1 for r in self.parsed_results if not r["display_line"].startswith("ERROR:"))
            error_count = len(self.parsed_results) - success_count
            self.status_label.config(text=f"找到 {len(self.parsed_results)} 个录像")
            logging.info(
                f"Parsing completed. Total: {len(self.parsed_results)}, Success: {success_count}, Errors: {error_count}")

            for info in self.parsed_results:
                display_text = f"{info['folder_name']} -> {info['display_line']}"
                self.result_listbox.insert(tk.END, display_text)

            if success_count > 0:
                self.export_stats_button.config(state=tk.NORMAL)  # type: ignore
        except Exception as e:
            logging.exception("Unexpected error during parsing")
            messagebox.showerror("解析错误", str(e))
            self.status_label.config(text="解析失败")

    def on_select(self, _) -> None:
        """Handle selection change in the listbox to enable ZIP export button."""
        if self.result_listbox.curselection():
            index = self.result_listbox.curselection()[0]
            if index < len(self.parsed_results):
                info = self.parsed_results[index]
                if not info["display_line"].startswith("ERROR:"):
                    self.export_zip_button.config(state=tk.NORMAL)  # type: ignore
                else:
                    self.export_zip_button.config(state=tk.DISABLED)  # type: ignore
            else:
                self.export_zip_button.config(state=tk.DISABLED)  # type: ignore
        else:
            self.export_zip_button.config(state=tk.DISABLED)  # type: ignore

    # noinspection PyBroadException
    def export_as_zip(self) -> None:
        """Export the selected replay folder as a ZIP archive."""
        selection = self.result_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个录像")
            logging.info("Export attempted without selection")
            return

        index = selection[0]
        if index >= len(self.parsed_results):
            messagebox.showerror("错误", "内部数据不一致")
            logging.error(f"Export index out of range: {index}")
            return

        info = self.parsed_results[index]
        if info["display_line"].startswith("ERROR:"):
            messagebox.showerror("错误", f"该录像解析失败，无法导出: {info['display_line']}")
            logging.error(f"Attempt to export error entry: {info['folder_name']}")
            return

        folder_path = Path(self.dir_var.get().strip()) / info["folder_name"]
        if not folder_path.exists() or not folder_path.is_dir():
            messagebox.showerror("错误", f"录像文件夹不存在: {folder_path}")
            logging.error(f"Folder not found: {folder_path}")
            return

        # Generate suggested ZIP filename with result
        zip_name = f"{info['folder_name']}({info['mode_name']}-{info['date_str']}-{info['time_str']}-{info['result_str']}-{info['map_name']}).zip"
        # Replace any characters that may be invalid in filenames
        invalid_chars = '<>:"/\\|?*'
        for ch in invalid_chars:
            zip_name = zip_name.replace(ch, '_')

        # Determine export path: use export_dir if valid, otherwise fallback to dialog
        export_dir = self.export_dir_var.get().strip()
        if export_dir:
            export_path = Path(export_dir)
            if not export_path.exists():
                messagebox.showerror("错误", f"导出目录不存在: {export_dir}")
                logging.error(f"Export directory does not exist: {export_dir}")
                return
            if not export_path.is_dir():
                messagebox.showerror("错误", f"导出路径不是目录: {export_dir}")
                logging.error(f"Export path is not a directory: {export_dir}")
                return
            # Check if writable (attempt to create a test file)
            try:
                test_file = export_path / ".write_test"
                test_file.touch()
                test_file.unlink()
            except Exception:
                messagebox.showerror("错误", f"导出目录不可写: {export_dir}")
                logging.error(f"Export directory not writable: {export_dir}")
                return

            file_path = export_path / zip_name
            # If file already exists, ask for overwrite confirmation
            if file_path.exists():
                if not messagebox.askyesno("文件已存在", f"文件 {zip_name} 已存在，是否覆盖？"):
                    logging.info("Export cancelled by user (overwrite declined)")
                    return
        else:
            # Fallback to file dialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
                title="保存ZIP文件",
                initialfile=zip_name
            )
            if not file_path:
                logging.info("Export cancelled by user")
                return
            file_path = Path(file_path)

        logging.info(f"Starting ZIP export: {folder_path} -> {file_path}")
        try:
            # Create ZIP archive
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in folder_path.rglob('*'):
                    if file.is_file():
                        archive_name = file.relative_to(folder_path.parent)
                        zipf.write(file, archive_name)
            messagebox.showinfo("成功", f"已导出ZIP文件到:\n{file_path}")
            logging.info(f"ZIP export successful: {file_path}")
        except PermissionError:
            logging.exception("Permission denied during ZIP creation")
            messagebox.showerror("导出错误", "没有权限写入目标文件或目录。")
        except OSError as e:
            logging.exception(f"OS error during ZIP creation: {e}")
            messagebox.showerror("导出错误", f"文件系统错误: {e}")
        except zipfile.BadZipFile as e:
            logging.exception(f"Bad ZIP file error: {e}")
            messagebox.showerror("导出错误", f"ZIP文件损坏: {e}")
        except Exception as e:
            logging.exception("Unexpected error during ZIP creation")
            messagebox.showerror("导出错误", f"未知错误: {e}")

    def export_statistics(self) -> None:
        """Export all parsed replay statistics to a CSV file."""
        if not self.parsed_results:
            messagebox.showinfo("提示", "没有可导出的统计数据")
            return

        # Filter out error entries
        valid_results = [r for r in self.parsed_results if not r["display_line"].startswith("ERROR:")]
        if not valid_results:
            messagebox.showinfo("提示", "没有成功解析的录像")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="保存统计数据",
            initialfile="replay_statistics.csv"
        )
        if not file_path:
            logging.info("Statistics export cancelled by user")
            return

        logging.info(f"Starting statistics export to {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["文件夹哈希", "游戏模式", "日期", "时间", "结果", "地图", "逃生人数"])
                for info in valid_results:
                    writer.writerow([
                        info["folder_name"],
                        info["mode_name"],
                        info["date_str"],
                        info["time_str"],
                        info["result_str"],
                        info["map_name"],
                        info["escape_count"]
                    ])
            messagebox.showinfo("成功", f"已导出 {len(valid_results)} 条统计数据到:\n{file_path}")
            logging.info(f"Statistics export successful: {file_path}")
        except Exception as e:
            logging.exception("Error during statistics export")
            messagebox.showerror("导出错误", str(e))

    def import_zips(self) -> None:
        """
        Import one or more ZIP files (exported by this tool) and extract them
        to the current replay root directory. After extraction, the folder
        (originally named with hash) is placed correctly, and the folder name
        is the hash part of the original ZIP filename. Also updates vmap.txt.
        """
        # Check if replay root directory is set and valid
        root_path_str = self.dir_var.get().strip()
        if not root_path_str:
            messagebox.showerror("错误", "请先设置录像根目录")
            logging.warning("Import attempted without root directory")
            return

        root_path = Path(root_path_str)
        if not root_path.exists() or not root_path.is_dir():
            messagebox.showerror("错误", f"录像根目录无效: {root_path}")
            logging.error(f"Invalid root directory: {root_path}")
            return

        # Let user select ZIP files
        zip_paths = filedialog.askopenfilenames(
            title="选择要导入的ZIP文件",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if not zip_paths:
            logging.info("Import cancelled by user")
            return

        success_count = 0
        error_count = 0

        for zip_path_str in zip_paths:
            zip_path = Path(zip_path_str)
            try:
                # Parse the hash part from the ZIP filename
                stem = zip_path.stem  # filename without .zip
                # Expected format: "hash(descriptive-part)"
                if '(' not in stem or ')' not in stem:
                    logging.warning(f"Skipping {zip_path.name}: not in expected format")
                    error_count += 1
                    continue

                start = stem.find('(')
                hash_part = stem[:start]
                if not hash_part:
                    logging.warning(f"Skipping {zip_path.name}: hash part empty")
                    error_count += 1
                    continue

                # Target folder path
                target_folder = root_path / hash_part

                # If target folder already exists, ask user
                if target_folder.exists():
                    if not messagebox.askyesno("文件夹已存在",
                                               f"文件夹 {hash_part} 已存在。\n是否覆盖？(将删除原有文件夹)"):
                        logging.info(f"Skipping {zip_path.name} due to existing folder")
                        continue
                    else:
                        # Remove existing folder
                        shutil.rmtree(target_folder)

                # Create a temporary directory for extraction
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)

                    # Extract ZIP to temporary directory
                    with zipfile.ZipFile(zip_path, 'r') as zipf:
                        zipf.extractall(tmp_path)

                    # Determine the content of the temporary directory
                    items = list(tmp_path.iterdir())

                    if len(items) == 1 and items[0].is_dir():
                        # Single directory: move it to target_folder
                        extracted_dir = items[0]
                        # Use shutil.move instead of rename to handle cross-drive moves
                        shutil.move(str(extracted_dir), str(target_folder))
                        logging.info(f"Imported {zip_path.name} -> {target_folder}")
                    else:
                        # Multiple files or single file: create target folder and move everything
                        target_folder.mkdir(parents=True, exist_ok=True)
                        for item in items:
                            dest = target_folder / item.name
                            # If dest exists, we overwrite (should not happen because we just removed target)
                            if dest.exists():
                                if dest.is_dir():
                                    shutil.rmtree(dest)
                                else:
                                    dest.unlink()
                            shutil.move(str(item), str(dest))
                        logging.info(f"Imported {zip_path.name} -> {target_folder} (created folder)")

                # Update vmap.txt for this imported replay using shared function
                update_vmap(root_path, hash_part, target_folder)

                success_count += 1

            except Exception as _:
                logging.exception(f"Failed to import {zip_path.name}")
                error_count += 1
                continue

        # Show summary
        messagebox.showinfo("导入完成",
                            f"成功导入 {success_count} 个文件，失败 {error_count} 个。\n"
                            "请点击“解析录像”刷新列表。")
        logging.info(f"Import completed. Success: {success_count}, Errors: {error_count}")


def main() -> None:
    """
    Main entry point for the GUI application.

    Sets up logging, creates the main window, and starts the Tkinter event loop.
    """
    # Get base directory for log file
    base_dir = get_base_dir()
    log_file = base_dir / "replay_parser.log"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()  # Also output to console (if any)
        ]
    )
    logging.info("=== Application started ===")

    root = tk.Tk()
    ReplayParserGui(root)
    root.mainloop()
    logging.info("Application closed")


if __name__ == "__main__":
    main()
