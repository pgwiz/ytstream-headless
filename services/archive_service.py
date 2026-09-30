import os
import shutil
import time
import zipfile
import uuid
import threading
from datetime import datetime
from flask import url_for
from config import temp_links, recent_downloads, recent_lock, cache_lock, TEMP_LINK_EXPIRY_SECONDS

AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.webm', '.opus', '.ogg', '.aac', '.wav', '.mp4', '.zip')

def safe_delete_files(folder_path, extension='.mp3'):
    """Safely delete files with given extension after archiving."""
    if not os.path.exists(folder_path):
        print(f"⚠️ Safe delete: folder {folder_path} does not exist")
        return
    
    deleted_count = 0
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(extension):
            filepath = os.path.join(folder_path, filename)
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"⚠️ Failed to delete {filepath}: {e}")
    
    print(f"🧹 Cleaned up {deleted_count} original audio files")

def create_split_archives(folder_path, archive_base_name, max_part_size_mb=100):
    """Creates multiple zip archive parts from audio files in folder_path."""
    if not os.path.exists(folder_path):
        print(f"❌ Archive creation failed: folder {folder_path} doesn't exist")
        return []
    
    max_part_size = max_part_size_mb * 1024 * 1024
    
    audio_files = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(AUDIO_EXTENSIONS) and not filename.lower().endswith('.zip'):
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                audio_files.append(file_path)
    
    if not audio_files:
        print(f"❌ No valid audio files found in {folder_path}")
        return []
    
    archives_created = []
    part_number = 1
    current_part_size = 0
    current_files = []
    
    def create_archive_name(num):
        return f"{archive_base_name}-part{str(num).zfill(2)}.zip"
    
    for file_path in audio_files:
        file_size = os.path.getsize(file_path)
        
        if current_part_size + file_size > max_part_size and current_files:
            archive_name = create_archive_name(part_number)
            archive_path = os.path.join(folder_path, archive_name)
            
            try:
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                    for current_file in current_files:
                        if os.path.exists(current_file):
                            arcname = os.path.basename(current_file)
                            zip_file.write(current_file, arcname=arcname)
                
                if os.path.exists(archive_path) and os.path.getsize(archive_path) > 0:
                    archives_created.append(archive_name)
            except Exception as e:
                print(f"❌ Error creating archive {archive_name}: {e}")
            
            part_number += 1
            current_part_size = 0
            current_files = []
        
        current_files.append(file_path)
        current_part_size += file_size
    
    if current_files:
        archive_name = create_archive_name(part_number)
        archive_path = os.path.join(folder_path, archive_name)
        
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                for current_file in current_files:
                    if os.path.exists(current_file):
                        arcname = os.path.basename(current_file)
                        zip_file.write(current_file, arcname=arcname)
            
            if os.path.exists(archive_path) and os.path.getsize(archive_path) > 0:
                archives_created.append(archive_name)
        except Exception as e:
            print(f"❌ Error creating final archive {archive_name}: {e}")
    
    return archives_created

def schedule_cleanup(path, delay):
    """Schedules a path for deletion after a delay."""
    def cleanup():
        time.sleep(delay)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    
    threading.Thread(target=cleanup, daemon=True).start()

def add_to_recent_downloads(filename, download_url, file_size_mb):
    """Add a download to the recent downloads list (thread-safe)."""
    with recent_lock:
        entry = {
            'filename': filename,
            'download_url': download_url,
            'size_mb': file_size_mb,
            'timestamp': time.time(),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        recent_downloads[:] = [r for r in recent_downloads if r['filename'] != filename]
        recent_downloads.insert(0, entry)
        
        if len(recent_downloads) > 5:
            recent_downloads[:] = recent_downloads[:5]
        
        return recent_downloads.copy()

def create_temp_link_for_file(file_path, folder_name, filename):
    """Create a download link for a file."""
    try:
        if not os.path.exists(file_path):
            return None
        
        from config import DOWNLOADS_DIR
        rel_path = os.path.relpath(file_path, DOWNLOADS_DIR).replace('\\', '/')
        
        import urllib.parse
        download_url = f"/downloads/{urllib.parse.quote(rel_path)}"
        return download_url
    except Exception as e:
        print(f"Failed to create link for {filename}: {e}")
        return None

def get_all_downloads():
    """Scans DOWNLOADS_DIR and returns list of all download files/archives."""
    from config import DOWNLOADS_DIR
    if not os.path.exists(DOWNLOADS_DIR):
        return []
    
    results = []
    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        for file in files:
            if file.lower().endswith(AUDIO_EXTENSIONS):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, DOWNLOADS_DIR).replace('\\', '/')
                size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
                mtime = os.path.getmtime(full_path)
                dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                import urllib.parse
                direct_url = f"/downloads/{urllib.parse.quote(rel_path)}"
                
                results.append({
                    'filename': file,
                    'path': rel_path,
                    'size_mb': size_mb,
                    'mtime': mtime,
                    'date': dt_str,
                    'download_url': f"{direct_url}?download=1",
                    'stream_url': direct_url,
                    'type': 'archive' if file.endswith('.zip') else 'audio'
                })
    
    results.sort(key=lambda x: x['mtime'], reverse=True)
    return results

def delete_download(target_path):
    """Deletes a specific download file or directory within DOWNLOADS_DIR cleanly."""
    from config import DOWNLOADS_DIR
    if not target_path or not os.path.exists(DOWNLOADS_DIR):
        return False, "File path is required"
    
    abs_downloads = os.path.abspath(DOWNLOADS_DIR)
    target_abs = os.path.abspath(os.path.join(DOWNLOADS_DIR, target_path))
    
    if not target_abs.startswith(abs_downloads):
        return False, "Permission denied: Invalid path traversal"
    
    if not os.path.exists(target_abs):
        return False, "File not found"
    
    try:
        if os.path.isdir(target_abs):
            shutil.rmtree(target_abs)
        else:
            os.remove(target_abs)
            parent = os.path.dirname(target_abs)
            if parent != abs_downloads and os.path.exists(parent) and not os.listdir(parent):
                shutil.rmtree(parent)
        
        with recent_lock:
            recent_downloads[:] = [r for r in recent_downloads if os.path.basename(target_abs) not in r['filename']]
        
        return True, "Successfully deleted target"
    except Exception as e:
        return False, f"Failed to delete file: {str(e)}"

def clear_all_downloads():
    """Clears all downloaded files and directories inside DOWNLOADS_DIR."""
    from config import DOWNLOADS_DIR
    if not os.path.exists(DOWNLOADS_DIR):
        return True, "Downloads folder empty"
    
    try:
        for item in os.listdir(DOWNLOADS_DIR):
            item_path = os.path.join(DOWNLOADS_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            elif os.path.exists(item_path):
                os.remove(item_path)
        
        with recent_lock:
            recent_downloads.clear()
        with cache_lock:
            temp_links.clear()
        
        return True, "All downloads cleared successfully"
    except Exception as e:
        return False, f"Error clearing downloads: {str(e)}"
