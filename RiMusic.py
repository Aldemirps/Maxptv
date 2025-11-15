#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiMusic - Downloader moderno com metadados OFICIAIS do Spotify
Versão Otimizada para Termux
Suave, limpo, com nome correto e playlists do YouTube
GPL-3.0
"""
import subprocess
import sys
import time
import threading
import re
import json
import requests
import os
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import itertools  # para animação suave

# ---------- CONFIGURAÇÃO DE LOG ----------
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger('RiMusic')

# ---------- CONSTANTES E PATHS ----------
SCRIPT_DIR = Path(__file__).resolve().parent
DOWN_DIR = SCRIPT_DIR / "downloads"
COOKIES = SCRIPT_DIR / "cookies.txt"
CONFIG_FILE = SCRIPT_DIR / "config.json"

# ---------- CONFIGURAÇÃO PADRÃO ----------
DEFAULT_CONFIG = {
    "format": "mp3",
    "tick": 30,
    "download_dir": str(DOWN_DIR),
    "media_type": "audio",
    "video_quality": "best",
    "audio_quality": "0"
}

# ---------- CREDENCIAIS SPOTIFY ----------
SPOTIFY_CREDS = {
    "client_id": "8abd627d9a2f48c9b615af1143a88273",
    "client_secret": "0aeb0fb255574dee98c75943986606e2"
}

# ---------- UTILITÁRIOS PARA TERMUX ----------
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class TermuxLogger:
    @staticmethod
    def info(message: str):
        print(f"{Color.CYAN}▪ {message}{Color.RESET}", file=sys.stderr)
    
    @staticmethod
    def success(message: str):
        print(f"{Color.GREEN}✅ {message}{Color.RESET}", file=sys.stderr)
    
    @staticmethod
    def warning(message: str):
        print(f"{Color.YELLOW}⚠ {message}{Color.RESET}", file=sys.stderr)
    
    @staticmethod
    def error(message: str):
        print(f"{Color.RED}❌ {message}{Color.RESET}", file=sys.stderr)

def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:100]

def ensure_directory(path: Path) -> Path:
    """Garante que o diretório existe"""
    path.mkdir(parents=True, exist_ok=True)
    return path

def check_dependencies() -> bool:
    """Verifica dependências otimizada para Termux"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            TermuxLogger.success("yt-dlp encontrado!")
            try:
                ffmpeg_check = subprocess.run(
                    ["yt-dlp", "--check-ffmpeg"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if ffmpeg_check.returncode != 0:
                    TermuxLogger.warning("FFmpeg não encontrado pelo yt-dlp, mas continuando...")
            except Exception:
                TermuxLogger.warning("FFmpeg check falhou, mas continuando...")
            return True
        else:
            raise subprocess.CalledProcessError(result.returncode, "yt-dlp")
    except Exception:
        TermuxLogger.error("yt-dlp não encontrado!")
        TermuxLogger.info("Instale com: pkg install yt-dlp")
        TermuxLogger.info("Ou: pip install yt-dlp")
        return False

def load_config() -> Dict[str, Any]:
    """Carrega configuração do arquivo"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            config = {**DEFAULT_CONFIG, **saved_config}
            TermuxLogger.success("Configuração carregada!")
            return config
        except Exception as e:
            TermuxLogger.error(f"Erro ao carregar configuração: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> bool:
    """Salva configuração no arquivo"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        TermuxLogger.success("Configuração salva!")
        return True
    except Exception as e:
        TermuxLogger.error(f"Erro ao salvar configuração: {e}")
        return False

# ---------- BARRA DE PROGRESSO SUAVE ----------
class SmoothProgress:
    def __init__(self, title: str):
        self.title = title[:40]
        self.percent = 0.0
        self.done = False
        self.spinner = itertools.cycle('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')

    def update(self, line: str):
        if "[download]" in line:
            if m := re.search(r'(\d+\.?\d*)%', line):
                self.percent = float(m.group(1))

    def _loop(self):
        while not self.done and self.percent < 100:
            print(f'\r{next(self.spinner)} {self.percent:3.0f}%  {self.title}',
                  end='', flush=True)
            time.sleep(0.15)
        print('\r' + ' ' * 60 + '\r', end='', flush=True)

    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.done = True
        if self.thread:
            self.thread.join(timeout=1)

# ---------- CLIENTE SPOTIFY ----------
def get_spotify_token() -> Optional[str]:
    """Obtém token de acesso do Spotify"""
    try:
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(SPOTIFY_CREDS["client_id"], SPOTIFY_CREDS["client_secret"]),
            timeout=15
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        TermuxLogger.error(f"Erro de autenticação Spotify: {e}")
        return None

def search_spotify_track(query: str, token: str) -> Optional[Dict[str, Any]]:
    """Busca track no Spotify"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": 1,
            "market": "US"
        }
        response = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params=params,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        items = data["tracks"]["items"]
        if not items:
            return None
        track = items[0]
        artists = ", ".join(artist["name"] for artist in track["artists"])
        return {
            "name": track["name"],
            "artist": artists,
            "album": track["album"]["name"],
            "track_number": track["track_number"],
            "track_count": track["album"]["total_tracks"],
            "date": track["album"]["release_date"],
            "genre": ";".join(track["album"].get("genres", [])),
            "search": f"{artists} - {track['name']}",
            "cover_url": track["album"]["images"][0]["url"] if track["album"].get("images") else None
        }
    except Exception as e:
        TermuxLogger.error(f"Erro na busca Spotify: {e}")
        return None

def get_spotify_playlist_tracks(playlist_id: str, token: str) -> List[Dict[str, Any]]:
    """Obtém todas as tracks de uma playlist do Spotify"""
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": 50, "market": "US"}
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            for item in data["items"]:
                track = item["track"]
                if track and track["type"] == "track":
                    artists = ", ".join(artist["name"] for artist in track["artists"])
                    tracks.append({
                        "name": track["name"],
                        "artist": artists,
                        "album": track["album"]["name"],
                        "track_number": track["track_number"],
                        "track_count": track["album"]["total_tracks"],
                        "date": track["album"]["release_date"],
                        "genre": ";".join(track["album"].get("genres", [])),
                        "search": f"{artists} - {track['name']}",
                        "cover_url": track["album"]["images"][0]["url"] if track["album"].get("images") else None
                    })
            url = data.get("next")
            params = None
    except Exception as e:
        TermuxLogger.error(f"Erro ao obter playlist: {e}")
    return tracks

def extract_spotify_playlist_id(url: str) -> Optional[str]:
    """Extrai ID da playlist do Spotify"""
    patterns = [
        r'playlist/([a-zA-Z0-9]+)',
        r'playlist/([a-zA-Z0-9]+)\?',
    ]
    for pattern in patterns:
        if match := re.search(pattern, url):
            return match.group(1)
    return None

# ---------- DOWNLOADER ----------
def download_with_metadata(metadata: Dict[str, Any], folder: Path, config: Dict[str, Any], 
                          cookies: Optional[Path] = None) -> bool:
    """Faz download com metadados do Spotify"""
    TermuxLogger.info(f"Baixando: {metadata['search']}")
    safe_name = sanitize_filename(metadata["search"])
    output_template = str(folder / f"{safe_name}.%(ext)s")
    cmd = [
        "yt-dlp",
        "ytsearch1:" + metadata["search"],
        "--extract-audio",
        "--audio-format", config["format"],
        "--audio-quality", config["audio_quality"],
        "--embed-metadata",
        "--embed-thumbnail",
        "--output", output_template,
        "--ignore-errors",
        "--no-overwrites",
        "--newline",
        "--concurrent-fragments", "3",
        "--socket-timeout", "15",
        "--retries", "5",
        "--fragment-retries", "5",
        "--throttled-rate", "100K",
    ]
    if cookies and cookies.exists():
        cmd.extend(["--cookies", str(cookies)])
    metadata_args = [
        "--parse-metadata", f"title:{metadata['name']}",
        "--parse-metadata", f"artist:{metadata['artist']}",
        "--parse-metadata", f"album:{metadata['album']}",
        "--parse-metadata", f"date:{metadata['date']}",
        "--add-metadata",
        "--postprocessor-args", f"ffmpeg:-metadata track={metadata['track_number']}/{metadata['track_count']}"
    ]
    if metadata.get("genre"):
        metadata_args.extend(["--parse-metadata", f"genre:{metadata['genre']}"])
    cmd.extend(metadata_args)
    progress = SmoothProgress(metadata["search"])
    progress.start()
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        for line in process.stdout:
            progress.update(line)
        process.wait()
        success = process.returncode == 0
    except Exception as e:
        TermuxLogger.error(f"Erro no download: {e}")
        success = False
    finally:
        progress.stop()
    if success:
        TermuxLogger.success(f"Concluído: {metadata['search']}")
    else:
        TermuxLogger.warning(f"Tentando fallback para: {metadata['search']}")
        success = download_fallback(metadata, folder, config, cookies)
    time.sleep(config["tick"])
    return success

def download_fallback(metadata: Dict[str, Any], folder: Path, config: Dict[str, Any], 
                     cookies: Optional[Path]) -> bool:
    """Tenta download alternativo"""
    fallback_terms = [
        metadata["search"] + " official audio",
        metadata["search"] + " lyrics",
        metadata["artist"] + " " + metadata["name"],
    ]
    for term in fallback_terms:
        try:
            cmd = [
                "yt-dlp",
                "ytsearch1:" + term,
                "--extract-audio",
                "--audio-format", config["format"],
                "--audio-quality", config["audio_quality"],
                "--embed-metadata",
                "--embed-thumbnail",
                "--output", str(folder / f"{sanitize_filename(metadata['search'])}.%(ext)s"),
                "--ignore-errors"
            ]
            if cookies and cookies.exists():
                cmd.extend(["--cookies", str(cookies)])
            result = subprocess.run(cmd, capture_output=True, timeout=120, text=True)
            if result.returncode == 0:
                TermuxLogger.success(f"Fallback bem-sucedido: {term}")
                return True
        except Exception:
            continue
    TermuxLogger.error(f"Falha definitiva: {metadata['search']}")
    return False

def download_youtube_playlist(url: str, folder: Path, config: Dict[str, Any], cookies: Optional[Path]) -> bool:
    """Baixa playlist completa do YouTube ou YouTube Music"""
    try:
        TermuxLogger.info("Baixando playlist do YouTube...")
        output_template = str(folder / "%(playlist_title)s" / "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp",
            url,
            "--yes-playlist",
            "--output", output_template,
            "--ignore-errors",
            "--no-overwrites",
            "--newline"
        ]
        if config["media_type"] == "audio":
            cmd.extend([
                "--extract-audio",
                "--audio-format", config["format"],
                "--audio-quality", config["audio_quality"],
                "--embed-metadata",
                "--embed-thumbnail"
            ])
        else:
            cmd.extend(["--format", config["video_quality"]])
        if cookies and cookies.exists():
            cmd.extend(["--cookies", str(cookies)])

        progress = SmoothProgress("Playlist do YouTube")
        progress.start()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        for line in process.stdout:
            progress.update(line)
        process.wait()
        progress.stop()
        if process.returncode == 0:
            TermuxLogger.success("Playlist baixada com sucesso!")
            return True
        else:
            TermuxLogger.error("Erro ao baixar playlist.")
            return False
    except Exception as e:
        TermuxLogger.error(f"Erro ao baixar playlist: {e}")
        return False

def download_from_url(url: str, folder: Path, config: Dict[str, Any], cookies: Optional[Path] = None) -> bool:
    """Download direto de URL – agora com nome correto e suporte a playlists do YouTube"""
    try:
        # Detecta se é playlist do YouTube / YouTube Music
        playlist_id = None
        if "list=" in url:
            playlist_match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
            if playlist_match:
                playlist_id = playlist_match.group(1)
                if playlist_id.startswith("PL") or playlist_id.startswith("OLAK5uy_"):
                    TermuxLogger.info("Playlist do YouTube detectada. Baixando todos os vídeos...")
                    return download_youtube_playlist(url, folder, config, cookies)

        # Caso não seja playlist, baixa único com nome correto
        TermuxLogger.info("Obtendo título do vídeo...")
        cmd_title = [
            "yt-dlp",
            "--print", "title",
            "--no-warnings",
            url
        ]
        result = subprocess.run(cmd_title, capture_output=True, text=True, timeout=15)
        title = result.stdout.strip() if result.returncode == 0 else None
        if not title:
            title = url.split("/")[-1] or "download"

        safe_title = sanitize_filename(title)
        output_template = str(folder / f"{safe_title}.%(ext)s")

        cmd = [
            "yt-dlp",
            url,
            "--output", output_template,
            "--ignore-errors",
            "--no-overwrites",
            "--newline"
        ]
        if config["media_type"] == "audio":
            cmd.extend([
                "--extract-audio",
                "--audio-format", config["format"],
                "--audio-quality", config["audio_quality"],
                "--embed-metadata",
                "--embed-thumbnail"
            ])
        else:
            cmd.extend(["--format", config["video_quality"]])
        if cookies and cookies.exists():
            cmd.extend(["--cookies", str(cookies)])

        progress = SmoothProgress(title)
        progress.start()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        for line in process.stdout:
            progress.update(line)
        process.wait()
        progress.stop()
        return process.returncode == 0
    except Exception as e:
        TermuxLogger.error(f"Erro no download de URL: {e}")
        return False

# ---------- INTERFACE DE USUÁRIO ----------
def clear_screen():
    """Limpa a tela do terminal"""
    os.system('clear')

def show_banner():
    """Exibe banner estilizado"""
    clear_screen()
    banner = f"""
{Color.CYAN}{'='*50}
{Color.BOLD}♪  RiMusic - Termux Edition  ♪{Color.RESET}
{Color.CYAN}{'='*50}{Color.RESET}
    """
    print(banner)

def about_screen():
    """Tela Sobre"""
    show_banner()
    info = f"""
{Color.BOLD}RiMusic - Versão Termux{Color.RESET}

{Color.CYAN}Características:{Color.RESET}
• Metadados OFICIAIS do Spotify
• Interface otimizada para Termux
• Download com progresso
• Suporte a playlists
• Configurações persistentes

{Color.YELLOW}Configuração automática:{Color.RESET}
• yt-dlp com ffmpeg integrado
• Paths otimizados para Termux
• Performance ajustada

{Color.GREEN}Licença: GPL-3.0{Color.RESET}
    """
    print(info)
    input(f"\n{Color.CYAN}Enter para voltar...{Color.RESET}")

def settings_menu(config: Dict[str, Any]):
    """Menu de configurações"""
    while True:
        show_banner()
        print(f"{Color.BOLD}--- CONFIGURAÇÕES ---{Color.RESET}\n")
        settings = [
            ("Tipo de mídia", config["media_type"]),
            ("Formato áudio", config["format"]),
            ("Qualidade áudio", config["audio_quality"]),
            ("Tick (segundos)", config["tick"]),
            ("Diretório", config["download_dir"]),
            ("Cookies", "✓" if COOKIES.exists() else "✗")
        ]
        for i, (name, value) in enumerate(settings, 1):
            print(f"{i}) {name:<18} → {value}")
        print(f"\n7) Restaurar padrões")
        print(f"0) Voltar")
        choice = input(f"\n{Color.GREEN}▶ {Color.RESET}").strip()
        if choice == "1":
            new_type = input("Tipo (audio/video): ").lower()
            if new_type in ["audio", "video"]:
                config["media_type"] = new_type
                save_config(config)
        elif choice == "2" and config["media_type"] == "audio":
            new_format = input("Formato (mp3/m4a/opus): ").lower()
            if new_format in ["mp3", "m4a", "opus"]:
                config["format"] = new_format
                save_config(config)
        elif choice == "3" and config["media_type"] == "audio":
            new_quality = input("Qualidade (0-9, 0=melhor): ").strip()
            if new_quality.isdigit() and 0 <= int(new_quality) <= 9:
                config["audio_quality"] = new_quality
                save_config(config)
        elif choice == "4":
            new_tick = input("Segundos entre downloads (1-999): ").strip()
            if new_tick.isdigit() and 1 <= int(new_tick) <= 999:
                config["tick"] = int(new_tick)
                save_config(config)
        elif choice == "5":
            new_dir = input("Novo diretório: ").strip()
            if new_dir:
                config["download_dir"] = new_dir
                save_config(config)
        elif choice == "6":
            manage_cookies()
        elif choice == "7":
            config.update(DEFAULT_CONFIG)
            save_config(config)
            TermuxLogger.success("Configurações restauradas!")
        elif choice == "0":
            break

def manage_cookies():
    """Gerencia cookies"""
    if COOKIES.exists():
        if input("Remover cookies? (s/n): ").strip().lower().startswith('s'):
            COOKIES.unlink(missing_ok=True)
            TermuxLogger.success("Cookies removidos!")
    else:
        if input("Importar cookies do navegador? (s/n): ").strip().lower().startswith('s'):
            browser = input("Navegador (firefox/chrome): ").strip().lower()
            if browser in ['firefox', 'chrome']:
                try:
                    subprocess.run([
                        "yt-dlp", "--cookies-from-browser", browser,
                        "--cookies", str(COOKIES)
                    ], check=True)
                    TermuxLogger.success("Cookies importados!")
                except subprocess.CalledProcessError as e:
                    TermuxLogger.error(f"Erro ao importar cookies: {e}")
            else:
                TermuxLogger.error("Navegador não suportado!")

def main_menu() -> str:
    """Menu principal"""
    show_banner()
    menu_items = [
        "1) Música por nome",
        "2) Playlist do Spotify", 
        "3) Arquivo .txt (lista)",
        "4) URL direta",
        "5) Configurações",
        "6) Sobre",
        "0) Sair"
    ]
    for item in menu_items:
        print(item)
    return input(f"\n{Color.GREEN}▶ {Color.RESET}").strip()

# ---------- FUNÇÕES PRINCIPAIS ----------
def single_download(config: Dict[str, Any]):
    """Download único por nome"""
    query = input("Nome da música/artista: ").strip()
    if not query:
        return
    folder = ensure_directory(Path(config["download_dir"]) / "Singles")
    cookies = COOKIES if COOKIES.exists() else None
    token = get_spotify_token()
    if not token:
        TermuxLogger.error("Não foi possível autenticar no Spotify")
        return
    metadata = search_spotify_track(query, token)
    if metadata:
        success = download_with_metadata(metadata, folder, config, cookies)
        if success:
            TermuxLogger.success("Download concluído!")
        else:
            TermuxLogger.error("Falha no download!")
    else:
        TermuxLogger.error("Música não encontrada no Spotify")

def spotify_playlist_download(config: Dict[str, Any]):
    """Download de playlist do Spotify"""
    url = input("URL da playlist Spotify: ").strip()
    if not url:
        return
    playlist_id = extract_spotify_playlist_id(url)
    if not playlist_id:
        TermuxLogger.error("URL da playlist inválida!")
        return
    token = get_spotify_token()
    if not token:
        TermuxLogger.error("Não foi possível autenticar no Spotify")
        return
    TermuxLogger.info("Obtendo tracks da playlist...")
    tracks = get_spotify_playlist_tracks(playlist_id, token)
    if not tracks:
        TermuxLogger.error("Playlist vazia ou não acessível!")
        return
    folder = ensure_directory(Path(config["download_dir"]) / f"Spotify_{playlist_id}")
    cookies = COOKIES if COOKIES.exists() else None
    TermuxLogger.info(f"Baixando {len(tracks)} músicas...")
    success_count = 0
    for i, track in enumerate(tracks, 1):
        TermuxLogger.info(f"{i}/{len(tracks)}: {track['search']}")
        if download_with_metadata(track, folder, config, cookies):
            success_count += 1
    TermuxLogger.success(f"Concluído: {success_count}/{len(tracks)} músicas")

def text_file_download(config: Dict[str, Any]):
    """Download a partir de arquivo de texto"""
    file_path = input("Caminho do arquivo .txt: ").strip()
    if not file_path:
        return
    txt_file = Path(file_path)
    if not txt_file.exists():
        TermuxLogger.error("Arquivo não encontrado!")
        return
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            items = [line.strip() for line in f if line.strip()]
    except Exception as e:
        TermuxLogger.error(f"Erro ao ler arquivo: {e}")
        return
    if not items:
        TermuxLogger.warning("Arquivo vazio!")
        return
    folder = ensure_directory(Path(config["download_dir"]) / sanitize_filename(txt_file.stem))
    cookies = COOKIES if COOKIES.exists() else None
    token = get_spotify_token()
    TermuxLogger.info(f"Processando {len(items)} itens...")
    success_count = 0
    for i, item in enumerate(items, 1):
        TermuxLogger.info(f"Item {i}/{len(items)}: {item}")
        if token and not item.startswith(('http://', 'https://')):
            metadata = search_spotify_track(item, token)
            if metadata:
                if download_with_metadata(metadata, folder, config, cookies):
                    success_count += 1
                continue
        if item.startswith(('http://', 'https://')):
            if download_from_url(item, folder, config, cookies):
                success_count += 1
        else:
            search_url = f"ytsearch1:{item}"
            if download_from_url(search_url, folder, config, cookies):
                success_count += 1
    TermuxLogger.success(f"Concluído: {success_count}/{len(items)}")

def url_download(config: Dict[str, Any]):
    """Download por URL direta"""
    url = input("URL do vídeo/áudio: ").strip()
    if not url:
        return
    folder = ensure_directory(Path(config["download_dir"]) / "URLs")
    cookies = COOKIES if COOKIES.exists() else None
    success = download_from_url(url, folder, config, cookies)
    if success:
        TermuxLogger.success("Download concluído!")
    else:
        TermuxLogger.error("Falha no download!")

# ---------- LOOP PRINCIPAL ----------
def main():
    """Função principal"""
    try:
        if not check_dependencies():
            sys.exit(1)
        config = load_config()
        ensure_directory(Path(config["download_dir"]))
        if not COOKIES.exists():
            COOKIES.touch()
        TermuxLogger.success("RiMusic iniciado no Termux!")
        while True:
            try:
                choice = main_menu()
                if choice == "1":
                    single_download(config)
                elif choice == "2":
                    spotify_playlist_download(config)
                elif choice == "3":
                    text_file_download(config)
                elif choice == "4":
                    url_download(config)
                elif choice == "5":
                    settings_menu(config)
                elif choice == "6":
                    about_screen()
                elif choice == "0":
                    TermuxLogger.success("Até logo! 👋")
                    break
                else:
                    TermuxLogger.error("Opção inválida!")
                input(f"\n{Color.CYAN}Enter para continuar...{Color.RESET}")
            except KeyboardInterrupt:
                TermuxLogger.warning("\nInterrompido pelo usuário")
                break
    except KeyboardInterrupt:
        TermuxLogger.warning("\nInterrompido pelo usuário")
    except Exception as e:
        TermuxLogger.error(f"Erro inesperado: {e}")
        logger.exception("Erro detalhado:")

if __name__ == "__main__":
    main()

